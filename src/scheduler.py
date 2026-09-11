"""
APScheduler 기반 자동화 스케줄러.

파이프라인은 2단계로 분리되어 있습니다 (회사 정책상 대외 발행은 담당자 승인 필요):

  1) run_pipeline()   — 매일 설정된 시각(KST)에 실행 (하루 여러 번 실행될 수 있음).
     뉴스 수집 → 필터 → 콘텐츠 생성 → 카드뉴스/블로그 이미지 생성 →
     output/pending/<draft_id>/manifest.json 에 "초안"으로 저장. draft_id 는
     "YYYY-MM-DD_HHMMSS" 형식의 실행 시각이라, 하루에 여러 번 실행돼도 서로
     덮어쓰지 않고 각각 별도 초안으로 남는다. 실제 SNS/블로그 발행 API는
     호출하지 않음.

  2) publish_pending(draft_id) — 담당자가 output/pending/<draft_id>/ 를 검토한 뒤
     `python main.py --publish <draft_id>` (또는 `latest`) 로 수동 실행. 이때
     비로소 Tistory / Instagram / Threads / Facebook 에 실제로 게시됨.
     일부 플랫폼만 실패한 경우 재시도 시 이미 성공한 플랫폼은 건너뛰어
     중복 게시를 방지한다 (manifest의 platform_results 에 결과 누적 기록).
"""

import json
import logging
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from src.news.fetcher import fetch_all_news, NewsItem
from src.news.filter import filter_news, top_items
from src.content.generator import GeneratedContent, generate_blog_post
from src.content.card_news import create_card_news
from src.content.blog_images import create_blog_images
from src.publishers.blog import TistoryPublisher
from src.publishers.instagram import InstagramPublisher
from src.publishers.threads import ThreadsPublisher
from src.publishers.facebook import FacebookPublisher

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")

PENDING_DIR = config.OUTPUT_DIR / "pending"
PUBLISHED_DIR = config.OUTPUT_DIR / "published"


# ── 1단계: 초안 생성 ──────────────────────────────────────────────────────────

def run_pipeline() -> dict:
    """
    뉴스 수집 → 콘텐츠 생성 → 이미지 생성까지 수행하고 초안을 저장.
    실제 SNS/블로그 발행은 하지 않는다 (담당자 승인 후 --publish 로 별도 실행).
    반환: 실행 결과 요약 dict.
    """
    now_dt = datetime.now(KST)
    now = now_dt.strftime("%Y-%m-%d %H:%M KST")
    draft_id = now_dt.strftime("%Y-%m-%d_%H%M%S")
    logger.info("═══ 초안 생성 파이프라인 시작: %s (draft_id=%s) ═══", now, draft_id)
    result: dict = {"started_at": now, "draft_id": draft_id, "steps": {}}

    # ── Step 1: 뉴스 수집 ──────────────────────────────────────────────────────
    try:
        raw_news = fetch_all_news()
        filtered = filter_news(raw_news)
        articles = top_items(filtered, limit=5)
        result["steps"]["news"] = {
            "total": len(raw_news),
            "filtered_re": len(filtered.real_estate),
            "filtered_gw": len(filtered.gwanak),
            "selected": len(articles),
        }
        logger.info("뉴스 수집 완료: %d건 선택", len(articles))
    except Exception:
        logger.error("뉴스 수집 실패:\n%s", traceback.format_exc())
        result["steps"]["news"] = {"error": traceback.format_exc()}
        return result

    if not articles:
        logger.warning("관련 기사 없음 — 파이프라인 중단")
        result["steps"]["news"]["skipped"] = True
        return result

    # ── Step 2: 콘텐츠 생성 (Claude API) ──────────────────────────────────────
    try:
        content = generate_blog_post(articles)
        result["steps"]["content"] = {"title": content.blog_title, "slides": len(content.card_slides)}
        logger.info("콘텐츠 생성 완료: %s", content.blog_title)
    except Exception:
        logger.error("콘텐츠 생성 실패:\n%s", traceback.format_exc())
        result["steps"]["content"] = {"error": traceback.format_exc()}
        return result

    if not content.blog_title:
        logger.warning("콘텐츠 생성 결과 비어있음 — 파이프라인 중단")
        return result

    # ── Step 3: 카드뉴스 이미지 생성 ─────────────────────────────────────────
    try:
        card_paths = create_card_news(content, draft_id=draft_id)
        result["steps"]["card_news"] = {"files": [str(p) for p in card_paths]}
        logger.info("카드뉴스 %d장 생성", len(card_paths))
    except Exception:
        logger.error("카드뉴스 생성 실패:\n%s", traceback.format_exc())
        result["steps"]["card_news"] = {"error": traceback.format_exc()}
        card_paths = []

    # ── Step 4: 블로그 썸네일/본문 이미지 생성 ────────────────────────────────
    try:
        blog_images = create_blog_images(content, draft_id=draft_id)
        result["steps"]["blog_images"] = {
            "thumbnail": str(blog_images["thumbnail"]) if blog_images["thumbnail"] else None,
            "body_images": [str(p) for p in blog_images["body_images"]],
        }
    except Exception:
        logger.error("블로그 이미지 생성 실패:\n%s", traceback.format_exc())
        result["steps"]["blog_images"] = {"error": traceback.format_exc()}
        blog_images = {"thumbnail": None, "body_images": []}

    # ── Step 5: 초안(manifest) 저장 — 발행은 아직 하지 않음 ───────────────────
    manifest_path = _save_manifest(draft_id, content, card_paths, blog_images)
    result["manifest"] = str(manifest_path)
    result["status"] = "pending_review"
    logger.info("═══ 초안 생성 완료 — 담당자 승인 대기: %s ═══", manifest_path)
    logger.info("발행하려면: python main.py --publish %s", draft_id)

    _save_run_log(result)
    return result


def _save_manifest(draft_id: str, content: GeneratedContent, card_paths: list[Path], blog_images: dict) -> Path:
    out_dir = PENDING_DIR / draft_id
    out_dir.mkdir(parents=True, exist_ok=True)

    data = asdict(content)
    # NewsItem 안의 datetime은 JSON 직렬화 불가 — 발행에 필요한 필드만 남김
    data["source_articles"] = [
        {"title": a.title, "link": a.link} for a in content.source_articles
    ]
    data["assets"] = {
        "card_news": [str(p) for p in card_paths],
        "blog_thumbnail": str(blog_images["thumbnail"]) if blog_images.get("thumbnail") else None,
        "blog_body_images": [str(p) for p in blog_images.get("body_images", [])],
    }
    data["draft_id"] = draft_id
    data["status"] = "pending_review"
    data["generated_at"] = datetime.now(KST).isoformat()
    data["platform_results"] = {}

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


# ── 2단계: 승인 후 실제 발행 ──────────────────────────────────────────────────

ALL_PLATFORMS = ("blog", "instagram", "threads", "facebook")


def list_pending() -> list[dict]:
    """승인 대기 중인 초안 목록 반환 (최신순). id는 --publish 에 넘길 draft_id."""
    if not PENDING_DIR.exists():
        return []
    items = []
    for d in sorted(PENDING_DIR.iterdir(), reverse=True):
        manifest_path = d / "manifest.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                items.append({
                    "id": d.name,
                    "date": data.get("date", ""),
                    "blog_title": data.get("blog_title", ""),
                    "generated_at": data.get("generated_at", ""),
                    "articles": len(data.get("source_articles", [])),
                    "platform_results": data.get("platform_results", {}),
                })
            except Exception as exc:
                logger.warning("manifest 읽기 실패 (%s): %s", manifest_path, exc)
    return items


def _load_manifest(draft_id: str) -> Optional[dict]:
    manifest_path = PENDING_DIR / draft_id / "manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _resolve_draft_id(draft_id: Optional[str]) -> Optional[str]:
    if draft_id and draft_id != "latest":
        return draft_id
    pending = list_pending()
    return pending[0]["id"] if pending else None


def _manifest_to_content(data: dict) -> GeneratedContent:
    source_articles = [
        NewsItem(title=a["title"], description="", link=a["link"])
        for a in data.get("source_articles", [])
    ]
    return GeneratedContent(
        date=data.get("date", ""),
        blog_title=data.get("blog_title", ""),
        blog_html=data.get("blog_html", ""),
        card_slides=data.get("card_slides", []),
        instagram_caption=data.get("instagram_caption", ""),
        threads_caption=data.get("threads_caption", ""),
        facebook_caption=data.get("facebook_caption", ""),
        hashtags=data.get("hashtags", []),
        highlight_quotes=data.get("highlight_quotes", []),
        source_articles=source_articles,
    )


def publish_pending(date: Optional[str] = None, platforms: Optional[list[str]] = None) -> dict:
    """
    담당자 승인 후 호출 — output/pending/<draft_id>/manifest.json 을 실제로 발행.
    date 에는 draft_id(예: 2026-09-10_180000) 또는 "latest" 를 넘긴다.
    platforms 를 지정하면 해당 플랫폼만 발행 (기본: 전체).
    이미 성공(status=ok)한 플랫폼은 재호출 시 자동으로 건너뛰어 중복 게시를 방지한다.
    """
    if platforms is not None:
        invalid = [p for p in platforms if p not in ALL_PLATFORMS]
        if invalid or not platforms:
            reason = (
                f"알 수 없는 플랫폼: {', '.join(invalid)}" if invalid else "플랫폼 목록이 비어 있습니다"
            )
            logger.error("%s (허용값: %s) — 아무것도 발행하지 않았습니다.", reason, ", ".join(ALL_PLATFORMS))
            return {"status": "error", "reason": reason}

    resolved_id = _resolve_draft_id(date)
    if not resolved_id:
        logger.error("승인 대기 중인 초안이 없습니다.")
        return {"status": "error", "reason": "승인 대기 중인 초안 없음"}

    data = _load_manifest(resolved_id)
    if not data:
        logger.error("초안을 찾을 수 없습니다: %s", resolved_id)
        return {"status": "error", "reason": f"{resolved_id} 초안 없음"}

    content = _manifest_to_content(data)
    assets = data.get("assets", {})
    card_paths = [Path(p) for p in assets.get("card_news", [])]
    blog_thumbnail = Path(assets["blog_thumbnail"]) if assets.get("blog_thumbnail") else None
    blog_body_images = [Path(p) for p in assets.get("blog_body_images", [])]

    existing_results: dict = data.get("platform_results", {})
    requested = platforms or list(ALL_PLATFORMS)
    already_done = [p for p in requested if existing_results.get(p, {}).get("status") == "ok"]
    targets = [p for p in requested if p not in already_done]

    published_at = datetime.now(KST).isoformat()
    attempt_results: dict = {}

    if already_done:
        logger.info("이미 발행 성공한 플랫폼은 건너뜀(중복 게시 방지): %s", ", ".join(already_done))

    if not targets:
        logger.info("발행할 대상이 없습니다 (요청한 플랫폼 모두 이미 발행 완료): %s", resolved_id)
    else:
        logger.info("═══ 발행 시작: %s (대상: %s) ═══", resolved_id, ", ".join(targets))

        if "blog" in targets:
            try:
                attempt_results["blog"] = TistoryPublisher().post(
                    content, thumbnail=blog_thumbnail, body_images=blog_body_images
                )
            except Exception as exc:
                logger.error("블로그 발행 실패: %s", exc)
                attempt_results["blog"] = {"status": "failed", "reason": str(exc)}

        if "instagram" in targets:
            try:
                attempt_results["instagram"] = InstagramPublisher().post_carousel(card_paths, content)
            except Exception as exc:
                logger.error("Instagram 발행 실패: %s", exc)
                attempt_results["instagram"] = {"status": "failed", "reason": str(exc)}

        if "threads" in targets:
            try:
                attempt_results["threads"] = ThreadsPublisher().post(card_paths, content)
            except Exception as exc:
                logger.error("Threads 발행 실패: %s", exc)
                attempt_results["threads"] = {"status": "failed", "reason": str(exc)}

        if "facebook" in targets:
            try:
                attempt_results["facebook"] = FacebookPublisher().post(card_paths, content)
            except Exception as exc:
                logger.error("Facebook 발행 실패: %s", exc)
                attempt_results["facebook"] = {"status": "failed", "reason": str(exc)}

    merged_results = {**existing_results, **attempt_results}
    fully_completed = _archive_published(resolved_id, data, merged_results, published_at)

    logger.info("═══ 발행 처리 완료: %s (전체 완료: %s) ═══", resolved_id, fully_completed)
    return {
        "date": resolved_id,
        "published_at": published_at,
        "results": attempt_results,
        "already_done": already_done,
        "fully_completed": fully_completed,
    }


def _archive_published(draft_id: str, manifest_data: dict, merged_results: dict, published_at: str) -> bool:
    """
    누적된 플랫폼별 발행 결과(merged_results)를 반영.
    ALL_PLATFORMS 전부가 ok/skipped 로 완료됐을 때만 output/published/ 로 옮기고
    pending 목록에서 제거한다. 아니면 pending manifest 에 결과를 누적 기록해두고
    유지 — 다음 --publish 재시도 시 이미 성공한 플랫폼은 자동으로 건너뛴다.
    반환: 이번 호출로 전 플랫폼 발행이 완료됐는지 여부.
    """
    manifest_data["platform_results"] = merged_results

    fully_completed = all(
        merged_results.get(p, {}).get("status") in ("ok", "skipped") for p in ALL_PLATFORMS
    )

    pending_manifest = PENDING_DIR / draft_id / "manifest.json"

    if fully_completed:
        manifest_data["status"] = "published"
        manifest_data["published_at"] = published_at

        out_dir = PUBLISHED_DIR / draft_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out_dir / "publish_result.json").write_text(
            json.dumps(
                {"draft_id": draft_id, "published_at": published_at, "results": merged_results},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )

        if pending_manifest.exists():
            pending_manifest.unlink()
        logger.info("모든 플랫폼 발행 완료 — 승인 대기 목록에서 제거: %s", draft_id)
    else:
        if pending_manifest.exists():
            pending_manifest.write_text(
                json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        logger.warning(
            "일부 플랫폼 미완료 — 승인 대기 목록에 유지 (재시도 시 완료된 플랫폼은 자동 건너뜀): %s",
            draft_id,
        )

    return fully_completed


def _save_run_log(result: dict) -> None:
    log_dir = config.OUTPUT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(KST).strftime("%Y%m%d_%H%M")
    path = log_dir / f"run_{ts}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug("실행 로그 저장: %s", path)


def start_scheduler() -> None:
    """APScheduler를 시작하고 설정된 시각에 초안 생성 파이프라인을 실행합니다."""
    scheduler = BlockingScheduler(timezone=KST)

    hours = config.SCHEDULE_HOURS
    if not hours:
        hours = [8, 18]

    hours_str = ",".join(str(h) for h in hours)
    trigger = CronTrigger(hour=hours_str, minute=0, timezone=KST)
    scheduler.add_job(run_pipeline, trigger=trigger, id="news_pipeline", name="뉴스 초안 생성 파이프라인")

    logger.info("스케줄러 시작 — 초안 생성 시각(KST): %s시", hours_str)
    logger.info("생성된 초안은 output/pending/ 에서 검토 후 --publish 로 발행하세요.")
    logger.info("Ctrl+C로 중지")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")

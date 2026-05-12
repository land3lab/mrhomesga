"""
APScheduler 기반 자동화 스케줄러.
매일 설정된 시각(KST)에 파이프라인 실행:
  뉴스 수집 → 필터 → 콘텐츠 생성 → 카드뉴스 → 블로그/Instagram 발행
"""

import json
import logging
import traceback
from datetime import datetime
from pathlib import Path

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from src.news.fetcher import fetch_all_news
from src.news.filter import filter_news, top_items
from src.content.generator import generate_blog_post
from src.content.card_news import create_card_news
from src.publishers.blog import TistoryPublisher
from src.publishers.instagram import InstagramPublisher

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")


def run_pipeline() -> dict:
    """
    전체 파이프라인 1회 실행.
    반환: 실행 결과 요약 dict.
    """
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    logger.info("═══ 파이프라인 시작: %s ═══", now)
    result: dict = {"started_at": now, "steps": {}}

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

    # ── Step 3: 카드뉴스 이미지 생성 ─────────────────────────────────────────
    try:
        card_paths = create_card_news(content)
        result["steps"]["card_news"] = {"files": [str(p) for p in card_paths]}
        logger.info("카드뉴스 %d장 생성", len(card_paths))
    except Exception:
        logger.error("카드뉴스 생성 실패:\n%s", traceback.format_exc())
        result["steps"]["card_news"] = {"error": traceback.format_exc()}
        card_paths = []

    # ── Step 4: 블로그 발행 ───────────────────────────────────────────────────
    try:
        blog_result = TistoryPublisher().post(content)
        result["steps"]["blog"] = blog_result
        logger.info("블로그 발행: %s", blog_result.get("url", "로컬 저장"))
    except Exception:
        logger.error("블로그 발행 실패:\n%s", traceback.format_exc())
        result["steps"]["blog"] = {"error": traceback.format_exc()}

    # ── Step 5: Instagram 발행 ─────────────────────────────────────────────────
    try:
        insta_result = InstagramPublisher().post_carousel(card_paths, content)
        result["steps"]["instagram"] = insta_result
        logger.info("Instagram 발행: %s", insta_result.get("status"))
    except Exception:
        logger.error("Instagram 발행 실패:\n%s", traceback.format_exc())
        result["steps"]["instagram"] = {"error": traceback.format_exc()}

    # ── 결과 로그 저장 ─────────────────────────────────────────────────────────
    _save_run_log(result)
    logger.info("═══ 파이프라인 완료 ═══")
    return result


def _save_run_log(result: dict) -> None:
    log_dir = config.OUTPUT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(KST).strftime("%Y%m%d_%H%M")
    path = log_dir / f"run_{ts}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug("실행 로그 저장: %s", path)


def start_scheduler() -> None:
    """APScheduler를 시작하고 설정된 시각에 파이프라인을 실행합니다."""
    scheduler = BlockingScheduler(timezone=KST)

    hours = config.SCHEDULE_HOURS
    if not hours:
        hours = [8, 18]

    hours_str = ",".join(str(h) for h in hours)
    trigger = CronTrigger(hour=hours_str, minute=0, timezone=KST)
    scheduler.add_job(run_pipeline, trigger=trigger, id="news_pipeline", name="뉴스 파이프라인")

    logger.info("스케줄러 시작 — 실행 시각(KST): %s시", hours_str)
    logger.info("Ctrl+C로 중지")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")

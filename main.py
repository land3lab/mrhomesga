#!/usr/bin/env python3
"""
Mr. Homes GA — 부동산 뉴스 자동 콘텐츠 생성 시스템
────────────────────────────────────────────────────
사용법:
  python main.py                    # 스케줄러 시작 (매일 설정된 시각에 "초안" 생성)
  python main.py --now              # 즉시 1회 초안 생성 (뉴스+콘텐츠+이미지, 발행은 안 함)
  python main.py --list-pending     # 승인 대기 중인 초안 목록 확인 (draft_id 확인용)
  python main.py --publish latest   # 가장 최근 초안을 실제 발행 (블로그+인스타+쓰레드+페북)
  python main.py --publish 2026-09-10_180000 --platforms blog,instagram
  python main.py --test             # 설정 검증만 수행

※ 회사 정책: SNS/블로그 등 대외 발행은 AI가 단독으로 확정하지 않습니다.
   --now 로 생성된 초안은 output/pending/<날짜>/ 에서 반드시 담당자가 검토한 뒤
   --publish 명령으로 직접 승인·발행하세요.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

Path("output/logs").mkdir(parents=True, exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("output/logs/mrhomesga.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


def _ensure_dirs() -> None:
    for sub in ("blog", "blog_images", "card_news", "logs", "pending", "published"):
        Path(f"output/{sub}").mkdir(parents=True, exist_ok=True)


def _test_config() -> None:
    import config
    logger.info("── 설정 검증 ──")

    fallback_msgs = {
        "NAVER_CLIENT_ID": "✗ (미설정 — 선택 사항. RSS 피드로 자동 대체되어 뉴스 수집엔 지장 없음)",
    }
    checks = {
        "ANTHROPIC_API_KEY": bool(config.ANTHROPIC_API_KEY),
        "NAVER_CLIENT_ID": bool(config.NAVER_CLIENT_ID),
        "TISTORY_ACCESS_TOKEN": bool(config.TISTORY_ACCESS_TOKEN),
        "INSTAGRAM_ACCESS_TOKEN": bool(config.INSTAGRAM_ACCESS_TOKEN),
        "THREADS_ACCESS_TOKEN": bool(config.THREADS_ACCESS_TOKEN),
        "FACEBOOK_PAGE_ACCESS_TOKEN": bool(config.FACEBOOK_PAGE_ACCESS_TOKEN),
    }
    for key, ok in checks.items():
        status = "✓" if ok else fallback_msgs.get(key, "✗ (미설정 — 해당 플랫폼은 로컬 저장/스킵으로 폴백)")
        logger.info("  %s: %s", key, status)
    logger.info("  SCHEDULE_HOURS(KST): %s", config.SCHEDULE_HOURS)
    logger.info("  KEYWORDS: %s", config.KEYWORDS)


def _list_pending() -> None:
    from src.scheduler import list_pending
    pending = list_pending()
    if not pending:
        logger.info("승인 대기 중인 초안이 없습니다.")
        return
    logger.info("── 승인 대기 초안 (%d건) ──", len(pending))
    for item in pending:
        done = [p for p, r in item["platform_results"].items() if r.get("status") == "ok"]
        done_note = f" | 발행 완료: {', '.join(done)}" if done else ""
        logger.info(
            "  %s | %s(%s) | 기사 %d건 | 생성: %s%s",
            item["id"], item["blog_title"], item["date"], item["articles"], item["generated_at"], done_note,
        )


def _publish(date: str, platforms_arg: str | None) -> None:
    from src.scheduler import publish_pending
    platforms = [p.strip() for p in platforms_arg.split(",")] if platforms_arg else None
    result = publish_pending(date=date, platforms=platforms)
    logger.info("발행 결과: %s", json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Mr. Homes GA 부동산 콘텐츠 자동화")
    parser.add_argument("--now", action="store_true", help="즉시 1회 초안 생성 (발행 안 함)")
    parser.add_argument("--test", action="store_true", help="설정 검증만")
    parser.add_argument("--list-pending", action="store_true", help="승인 대기 중인 초안 목록")
    parser.add_argument(
        "--publish", metavar="DRAFT_ID",
        help="지정 초안(--list-pending 에서 확인한 draft_id, 예: 2026-09-10_180000) 또는 'latest' 를 실제 발행",
    )
    parser.add_argument(
        "--platforms", metavar="blog,instagram,threads,facebook",
        help="--publish 와 함께 사용, 발행 대상 플랫폼 제한 (기본: 전체)",
    )
    args = parser.parse_args()

    _ensure_dirs()

    if args.test:
        _test_config()
        return

    if args.list_pending:
        _list_pending()
        return

    if args.publish:
        _publish(args.publish, args.platforms)
        return

    if args.now:
        logger.info("즉시 초안 생성 모드 (발행 없음)")
        from src.scheduler import run_pipeline
        result = run_pipeline()
        logger.info("결과: %s", json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    # 기본: 스케줄러 시작 (초안 생성만 자동화, 발행은 항상 수동 승인)
    from src.scheduler import start_scheduler
    start_scheduler()


if __name__ == "__main__":
    main()

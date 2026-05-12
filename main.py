#!/usr/bin/env python3
"""
Mr. Homes GA — 관악구 부동산 뉴스 자동 포스팅 시스템
────────────────────────────────────────────────────
사용법:
  python main.py           # 스케줄러 시작 (매일 설정된 시각 자동 실행)
  python main.py --now     # 즉시 1회 실행
  python main.py --test    # 설정 검증만 수행
"""

import argparse
import logging
import sys
from pathlib import Path

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
    for sub in ("blog", "card_news", "logs"):
        Path(f"output/{sub}").mkdir(parents=True, exist_ok=True)


def _test_config() -> None:
    import config
    logger.info("── 설정 검증 ──")
    checks = {
        "ANTHROPIC_API_KEY": bool(config.ANTHROPIC_API_KEY),
        "NAVER_CLIENT_ID": bool(config.NAVER_CLIENT_ID),
        "TISTORY_ACCESS_TOKEN": bool(config.TISTORY_ACCESS_TOKEN),
        "INSTAGRAM_ACCESS_TOKEN": bool(config.INSTAGRAM_ACCESS_TOKEN),
    }
    for key, ok in checks.items():
        status = "✓" if ok else "✗ (미설정)"
        logger.info("  %s: %s", key, status)
    logger.info("  SCHEDULE_HOURS(KST): %s", config.SCHEDULE_HOURS)
    logger.info("  KEYWORDS: %s", config.KEYWORDS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mr. Homes GA 자동 포스팅")
    parser.add_argument("--now", action="store_true", help="즉시 1회 실행")
    parser.add_argument("--test", action="store_true", help="설정 검증만")
    args = parser.parse_args()

    _ensure_dirs()

    if args.test:
        _test_config()
        return

    if args.now:
        logger.info("즉시 실행 모드")
        from src.scheduler import run_pipeline
        result = run_pipeline()
        logger.info("결과: %s", result)
        return

    # 기본: 스케줄러 시작
    from src.scheduler import start_scheduler
    start_scheduler()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Mr. Homes GA — 관악구 부동산 뉴스 자동 포스팅 시스템
────────────────────────────────────────────────────
사용법:
  python main.py             # 스케줄러 시작 (매일 설정된 시각 자동 실행)
  python main.py --now       # 즉시 1회 실행
  python main.py --demo      # 샘플 데이터로 카드뉴스 생성 (API 키 불필요)
  python main.py --test      # 설정 검증만 수행
"""

import argparse
import logging
import sys
from pathlib import Path

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


def _run_demo() -> None:
    """샘플 뉴스 데이터로 카드뉴스 이미지와 HTML 미리보기를 생성."""
    import config
    from src.news.demo_data import SAMPLE_NEWS
    from src.content.models import GeneratedContent
    from src.content.card_news import create_card_news
    from datetime import datetime

    logger.info("── 데모 모드: 샘플 데이터로 카드뉴스 생성 ──")

    # API 없이 미리 정의된 콘텐츠 구조 사용
    today = datetime.now().strftime("%Y-%m-%d")
    content = GeneratedContent(
        date=today,
        blog_title=f"[{today}] 관악구 부동산 주간 브리핑 — 신림 재개발·전세 하락 외",
        blog_html="<p>데모 모드에서는 블로그 HTML이 생성되지 않습니다.</p>",
        card_slides=[
            {
                "title": "오늘의 부동산",
                "body": "관악구 핵심 뉴스 5가지를 한눈에",
            },
            {
                "title": "신림 재개발",
                "body": "신림동 조합 설립 인가 완료\n2000세대 규모, 2027년 착공 목표",
            },
            {
                "title": "서울 전세 하락",
                "body": "3주 연속 하락세\n관악구 -0.18% 서울 평균 웃돌아",
            },
            {
                "title": "서울대입구 월세",
                "body": "오피스텔 월세 전년비 +8%\n1인 가구 수요 급증이 원인",
            },
            {
                "title": "신림선 연장",
                "body": "여의도까지 15분 단축\n2030년 완공 목표 — 교통 호재",
            },
            {
                "title": "팔로우 하세요!",
                "body": "매일 아침 관악구 부동산 뉴스\nMr. Homes GA와 함께",
            },
        ],
        instagram_caption=(
            "📰 오늘의 관악구 부동산 뉴스\n\n"
            "신림 재개발 조합 설립 인가부터 전세 하락세까지,\n"
            "관악구 주민이 꼭 알아야 할 소식을 정리했어요.\n\n"
            "👇 카드 넘겨보세요!"
        ),
        hashtags=[
            "#관악구부동산", "#신림동재개발", "#전세하락", "#서울대입구",
            "#관악구아파트", "#서울부동산", "#부동산뉴스", "#신림선연장",
            "#오늘의부동산", "#관악구월세", "#아파트전세", "#부동산투자",
            "#실거주", "#관악구", "#MrHomesGA",
        ],
        source_articles=SAMPLE_NEWS,
    )

    paths = create_card_news(content)

    if paths:
        preview = paths[0].parent / "preview.html"
        logger.info("✓ 카드뉴스 %d장 생성 완료", len(paths))
        logger.info("✓ HTML 미리보기: %s", preview.resolve())
        logger.info("  브라우저에서 위 경로를 열어 확인하세요.")
    else:
        logger.error("카드뉴스 생성 실패")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mr. Homes GA 자동 포스팅")
    parser.add_argument("--now", action="store_true", help="즉시 1회 실행 (API 키 필요)")
    parser.add_argument("--demo", action="store_true", help="샘플 데이터로 카드뉴스 생성 (API 키 불필요)")
    parser.add_argument("--test", action="store_true", help="설정 검증만")
    args = parser.parse_args()

    _ensure_dirs()

    if args.test:
        _test_config()
        return

    if args.demo:
        _run_demo()
        return

    if args.now:
        logger.info("즉시 실행 모드")
        from src.scheduler import run_pipeline
        result = run_pipeline()
        logger.info("결과: %s", result)
        return

    from src.scheduler import start_scheduler
    start_scheduler()


if __name__ == "__main__":
    main()

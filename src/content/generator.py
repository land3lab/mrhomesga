"""
Claude API를 이용한 콘텐츠 생성.
- 블로그 포스트 (HTML)
- 카드뉴스 텍스트 (슬라이드별 짧은 문장)
- 인스타그램 캡션 + 해시태그
"""

import json
import logging
from datetime import datetime

import anthropic

import config
from src.news.fetcher import NewsItem
from src.content.models import GeneratedContent

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _build_news_summary(items: list[NewsItem]) -> str:
    parts = []
    for i, item in enumerate(items, 1):
        parts.append(
            f"[기사 {i}]\n제목: {item.title}\n요약: {item.description[:300]}\n출처: {item.link}"
        )
    return "\n\n".join(parts)


def generate_blog_post(items: list[NewsItem]) -> GeneratedContent:
    """뉴스 기사들을 바탕으로 블로그 포스트 + 카드뉴스 + 인스타 캡션 생성."""
    if not items:
        logger.warning("생성할 뉴스 기사가 없습니다.")
        return GeneratedContent()

    news_text = _build_news_summary(items)
    today = datetime.now().strftime("%Y년 %m월 %d일")

    prompt = f"""당신은 서울시 관악구 부동산 전문 SNS 콘텐츠 에디터입니다.
아래 {len(items)}개의 뉴스 기사를 바탕으로 오늘({today}) 발행할 콘텐츠를 JSON으로 생성하세요.

## 입력 뉴스 기사
{news_text}

## 출력 JSON 구조 (반드시 준수)
{{
  "blog_title": "SEO 최적화 블로그 제목 (50자 이내, 핵심 키워드 포함)",
  "blog_html": "HTML 블로그 포스트 (h2/h3/p/ul 태그, 800~1200자, 관악구 주민 관점 인사이트)",
  "card_slides": [
    {{"title": "표지 제목 (15자 이내)", "body": "오늘의 주요 뉴스 한 줄 요약 (30자 이내)"}},
    {{"title": "뉴스1 핵심어 (12자 이내)", "body": "구체적 수치/사실 중심 설명 (60자 이내)"}},
    {{"title": "뉴스2 핵심어 (12자 이내)", "body": "구체적 수치/사실 중심 설명 (60자 이내)"}},
    {{"title": "뉴스3 핵심어 (12자 이내)", "body": "구체적 수치/사실 중심 설명 (60자 이내)"}},
    {{"title": "전망·인사이트 (12자 이내)", "body": "관악구 주민이 알아야 할 포인트 (60자 이내)"}},
    {{"title": "팔로우 요청 (10자 이내)", "body": "채널 소개 + 구독 유도 문구 (40자 이내)"}}
  ],
  "instagram_caption": "첫 줄 강렬한 훅 문장\\n\\n본문 2~3줄 (실용적 정보)\\n\\n마지막 줄 CTA (200자 이내)",
  "hashtags": ["#관악구부동산", "#신림동", "#봉천동", "#낙성대", "#서울대입구", "#관악구아파트",
               "#서울부동산", "#아파트", "#전세", "#월세", "#분양", "#재개발", "#부동산뉴스",
               "#오늘의부동산", "#부동산투자", "#실거주", "#관악구맛집X", "#MrHomesGA"]
}}

## 제약 조건
- card_slides: 정확히 6개 (표지1 + 본문4 + CTA1)
- 슬라이드 제목/본문은 한국어, 간결하고 명확하게
- 기사에 없는 수치나 사실 절대 추측 금지
- hashtags는 주어진 예시를 기반으로 실제 기사 내용과 관련된 태그로 교체 가능

JSON만 출력하세요."""

    raw = ""
    try:
        client = _get_client()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            system="당신은 부동산 SNS 콘텐츠 전문가입니다. 요청한 JSON 형식만 정확히 출력합니다.",
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0]
        data = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        logger.error("JSON 파싱 실패: %s\n원문: %.500s", exc, raw)
        return GeneratedContent(source_articles=items)
    except Exception as exc:
        logger.error("Claude API 오류: %s", exc)
        return GeneratedContent(source_articles=items)

    content = GeneratedContent(
        blog_title=data.get("blog_title", ""),
        blog_html=data.get("blog_html", ""),
        card_slides=data.get("card_slides", []),
        instagram_caption=data.get("instagram_caption", ""),
        hashtags=data.get("hashtags", []),
        source_articles=items,
    )
    logger.info("콘텐츠 생성 완료 — 제목: %s", content.blog_title)
    return content


def build_instagram_caption(content: GeneratedContent) -> str:
    """인스타그램용 최종 캡션 조합 (본문 + 해시태그)."""
    tags = " ".join(content.hashtags)
    return f"{content.instagram_caption}\n\n{tags}"

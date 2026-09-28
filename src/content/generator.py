"""
Claude API를 이용한 콘텐츠 생성.
- 블로그 포스트 (HTML)
- 카드뉴스 텍스트 (슬라이드별 짧은 문장)
- 인스타그램 캡션 + 해시태그
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

import anthropic

import config
from src.news.fetcher import NewsItem

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


@dataclass
class GeneratedContent:
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    blog_title: str = ""
    blog_html: str = ""
    card_slides: list[dict] = field(default_factory=list)  # [{title, body}, ...]
    instagram_caption: str = ""
    threads_caption: str = ""
    facebook_caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    highlight_quotes: list[str] = field(default_factory=list)  # 블로그 본문 삽입 이미지용 핵심 문장 2~3개
    source_articles: list[NewsItem] = field(default_factory=list)


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

    prompt = f"""당신은 서울시 관악구 부동산 전문 콘텐츠 작가입니다.
아래 {len(items)}개의 뉴스 기사를 바탕으로 오늘({today}) 발행할 콘텐츠를 JSON으로 생성해주세요.

## 입력 뉴스 기사
{news_text}

## 출력 형식 (반드시 아래 JSON 구조 준수)
{{
  "blog_title": "SEO 최적화된 블로그 제목 (60자 이내)",
  "blog_html": "완전한 HTML 블로그 포스트 (h2/h3/p/ul 사용, 1000~1500자, 핵심 인사이트 + 관악구 주민 관점)",
  "card_slides": [
    {{"title": "슬라이드 제목 (20자 이내)", "body": "핵심 내용 (50자 이내)"}},
    ...
  ],
  "instagram_caption": "인스타그램 캡션 (감성적이고 실용적, 200자 이내, 줄바꿈 포함)",
  "threads_caption": "쓰레드(Threads)용 캡션 (짧고 대화체, 500자 이내, 질문/의견을 유도하는 톤)",
  "facebook_caption": "페이스북용 캡션 (정보 전달 중심, 300~500자, 문단 구분 포함)",
  "hashtags": ["#관악구부동산", "#서울부동산", ...],
  "highlight_quotes": ["블로그 본문 이미지에 큼직하게 넣을 핵심 한 줄 요약 1", "핵심 한 줄 요약 2"]
}}

## 조건
- card_slides: 5~7개 슬라이드 (첫 번째는 표지, 마지막은 행동 유도)
- hashtags: 15~20개 (관악구, 신림, 부동산, 아파트, 전세, 월세 등 관련 태그 포함)
- highlight_quotes: 2~3개, 각 40자 이내의 임팩트 있는 한 줄 (숫자/시세/정책 변화 등 핵심 사실 우선)
- 전문적이지만 이해하기 쉬운 문체
- 부정확한 정보 추측 금지 — 기사에 있는 내용만 사용

JSON만 출력하세요. 다른 텍스트 없이."""

    try:
        client = _get_client()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            system="당신은 부동산 콘텐츠 전문가입니다. 요청한 JSON 형식만 정확히 출력합니다.",
        )
        raw = message.content[0].text.strip()
        # JSON 코드블록 제거
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("JSON 파싱 실패: %s\n원문: %s", exc, raw[:500])
        return GeneratedContent(source_articles=items)
    except Exception as exc:
        logger.error("Claude API 오류: %s", exc)
        return GeneratedContent(source_articles=items)

    content = GeneratedContent(
        blog_title=data.get("blog_title", ""),
        blog_html=data.get("blog_html", ""),
        card_slides=data.get("card_slides", []),
        instagram_caption=data.get("instagram_caption", ""),
        threads_caption=data.get("threads_caption", ""),
        facebook_caption=data.get("facebook_caption", ""),
        hashtags=data.get("hashtags", []),
        highlight_quotes=data.get("highlight_quotes", []),
        source_articles=items,
    )
    logger.info("콘텐츠 생성 완료 — 제목: %s", content.blog_title)
    return content


def build_instagram_caption(content: GeneratedContent) -> str:
    """인스타그램용 최종 캡션 조합 (본문 + 해시태그)."""
    tags = " ".join(content.hashtags)
    return f"{content.instagram_caption}\n\n{tags}"


def build_threads_caption(content: GeneratedContent) -> str:
    """쓰레드용 최종 캡션 조합 (본문 + 핵심 해시태그 소수)."""
    tags = " ".join(content.hashtags[:5])
    text = content.threads_caption or content.instagram_caption
    return f"{text}\n\n{tags}".strip()


def build_facebook_caption(content: GeneratedContent) -> str:
    """페이스북용 최종 캡션 조합 (본문 + 해시태그)."""
    tags = " ".join(content.hashtags)
    text = content.facebook_caption or content.instagram_caption
    return f"{text}\n\n{tags}".strip()

"""
뉴스 수집 모듈
- Naver Search API (뉴스 검색)
- RSS 피드 폴백 (네이버/다음 등)
"""

import logging
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import feedparser
import requests

import config

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    # 네이버 부동산 뉴스 RSS
    "https://rss.naver.com/main/rss.naver?blogId=naver_property",
    # 주요 언론사 부동산 RSS
    "https://www.chosun.com/arc/outboundfeeds/rss/category/real-estate/?outputType=xml",
    "https://rss.joins.com/joins_news_list.xml",
    "https://www.hani.co.kr/rss/",
    "https://www.khan.co.kr/rss/rssdata/kh_realestate.xml",
    "https://www.mk.co.kr/rss/30000001/",      # 매일경제 부동산
    "https://www.hankyung.com/feed/realestate",  # 한국경제 부동산
]

NAVER_NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"


@dataclass
class NewsItem:
    title: str
    description: str
    link: str
    published: Optional[datetime] = None
    source: str = ""
    keywords_matched: list = field(default_factory=list)


def _fetch_naver_api(query: str, display: int = 20) -> list[NewsItem]:
    """Naver Search API로 뉴스 검색."""
    if not config.NAVER_CLIENT_ID or not config.NAVER_CLIENT_SECRET:
        logger.debug("Naver API 키 미설정 — RSS 폴백 사용")
        return []

    headers = {
        "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
    }
    params = {
        "query": query,
        "display": display,
        "sort": "date",
    }
    try:
        resp = requests.get(NAVER_NEWS_API_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        results = []
        for it in items:
            title = _strip_html(it.get("title", ""))
            desc = _strip_html(it.get("description", ""))
            pub_str = it.get("pubDate", "")
            pub = _parse_rfc822(pub_str)
            results.append(NewsItem(
                title=title,
                description=desc,
                link=it.get("originallink") or it.get("link", ""),
                published=pub,
                source="naver_api",
            ))
        return results
    except Exception as exc:
        logger.warning("Naver API 오류: %s", exc)
        return []


def _fetch_rss(url: str) -> list[NewsItem]:
    """RSS 피드에서 뉴스 파싱."""
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "MrHomesGA/1.0"})
        results = []
        for entry in feed.entries:
            title = entry.get("title", "")
            desc = _strip_html(entry.get("summary", entry.get("description", "")))
            link = entry.get("link", "")
            pub = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub = datetime(*entry.published_parsed[:6])
            results.append(NewsItem(
                title=title,
                description=desc,
                link=link,
                published=pub,
                source=url,
            ))
        return results
    except Exception as exc:
        logger.warning("RSS 파싱 오류 (%s): %s", url, exc)
        return []


def fetch_all_news() -> list[NewsItem]:
    """모든 소스에서 뉴스를 수집하여 반환."""
    items: list[NewsItem] = []

    # 1) Naver API — 핵심 키워드 검색
    for kw in ["부동산 관악구", "서울 관악 아파트", "부동산 서울"]:
        items.extend(_fetch_naver_api(kw, display=20))

    # 2) RSS 폴백
    if not items:
        logger.info("Naver API 결과 없음 — RSS 피드 수집")
        for url in RSS_FEEDS:
            items.extend(_fetch_rss(url))

    # 중복 제거 (link 기준)
    seen: set[str] = set()
    unique: list[NewsItem] = []
    for item in items:
        if item.link and item.link not in seen:
            seen.add(item.link)
            unique.append(item)

    logger.info("총 %d건 수집 (중복 제거 후)", len(unique))
    return unique


# ── helpers ──────────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """간단한 HTML 태그 제거."""
    import re
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_rfc822(date_str: str) -> Optional[datetime]:
    from email.utils import parsedate
    import calendar
    try:
        t = parsedate(date_str)
        if t:
            return datetime(*t[:6])
    except Exception:
        pass
    return None

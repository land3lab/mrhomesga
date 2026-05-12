"""
수집된 뉴스를 부동산 / 서울시 관악구 기준으로 필터링.
"""

import logging
from dataclasses import dataclass, field

from src.news.fetcher import NewsItem
import config

logger = logging.getLogger(__name__)


@dataclass
class FilteredNews:
    real_estate: list[NewsItem] = field(default_factory=list)
    gwanak: list[NewsItem] = field(default_factory=list)
    combined: list[NewsItem] = field(default_factory=list)  # 두 조건 모두 해당


def _matches(item: NewsItem, keywords: list[str]) -> list[str]:
    """뉴스 제목·본문에서 매칭된 키워드 목록 반환."""
    text = (item.title + " " + item.description).lower()
    return [kw for kw in keywords if kw in text]


def filter_news(items: list[NewsItem]) -> FilteredNews:
    """
    - real_estate: 부동산 키워드 포함
    - gwanak: 관악구 키워드 포함
    - combined: 두 조건 동시 충족 (우선 게시 대상)
    """
    result = FilteredNews()

    for item in items:
        re_matches = _matches(item, config.REAL_ESTATE_KEYWORDS)
        gw_matches = _matches(item, config.GWANAK_KEYWORDS)

        if re_matches:
            item.keywords_matched = re_matches
            result.real_estate.append(item)

        if gw_matches:
            if item not in result.gwanak:
                result.gwanak.append(item)

        if re_matches and gw_matches:
            result.combined.append(item)

    logger.info(
        "필터 결과 — 부동산: %d건 / 관악구: %d건 / 복합: %d건",
        len(result.real_estate),
        len(result.gwanak),
        len(result.combined),
    )
    return result


def top_items(filtered: FilteredNews, limit: int = 5) -> list[NewsItem]:
    """
    콘텐츠 생성에 쓸 상위 기사 선정.
    우선순위: combined > gwanak > real_estate
    """
    seen: set[str] = set()
    selected: list[NewsItem] = []

    for pool in (filtered.combined, filtered.gwanak, filtered.real_estate):
        for item in pool:
            if item.link not in seen and len(selected) < limit:
                seen.add(item.link)
                selected.append(item)

    return selected

"""
카드뉴스 / 블로그 이미지 생성 공통 유틸.
- 한글 폰트 로딩
- 텍스트 줄바꿈
"""

import logging
import textwrap
from pathlib import Path

from PIL import ImageFont

logger = logging.getLogger(__name__)
_warned_missing_font = False

# 한글 글리프를 지원하는 폰트만 (우선순위 순)
_KOREAN_FONT_CANDIDATES_REGULAR = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
_KOREAN_FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]
# 한글 미지원 — 한글 폰트가 전혀 없을 때의 최후 폴백(영문/숫자만 정상 렌더링됨)
_FALLBACK_FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FALLBACK_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

_font_cache: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """시스템 한글 폰트 로드 — 없으면 기본 폰트. 결과는 캐시됨."""
    global _warned_missing_font
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]

    korean_candidates = _KOREAN_FONT_CANDIDATES_BOLD if bold else _KOREAN_FONT_CANDIDATES_REGULAR
    font = None
    for path in korean_candidates:
        if Path(path).exists():
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue

    if font is None:
        if not _warned_missing_font:
            logger.warning(
                "한글 지원 폰트를 찾지 못했습니다 (%s) — 생성된 이미지의 한글이 깨져 보일 수 있습니다. "
                "`sudo apt install fonts-nanum` 또는 `fonts-noto-cjk` 설치를 권장합니다.",
                ", ".join(_KOREAN_FONT_CANDIDATES_REGULAR),
            )
            _warned_missing_font = True

        fallback_path = _FALLBACK_FONT_BOLD if bold else _FALLBACK_FONT_REGULAR
        try:
            font = ImageFont.truetype(fallback_path, size) if Path(fallback_path).exists() else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

    _font_cache[key] = font
    return font


def wrap_text(text: str, width: int) -> list[str]:
    """긴 문장을 지정 폭으로 줄바꿈."""
    return textwrap.wrap(text, width=width)

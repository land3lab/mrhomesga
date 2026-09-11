"""
Pillow를 이용한 블로그 대표 썸네일 + 본문 삽입 이미지 생성.
- 썸네일: 1200×630 (OpenGraph 표준, 블로그 목록/공유 미리보기용)
- 본문 이미지: 1200×675, highlight_quotes 기반 핵심 한 줄 카드 (0~3장)
"""

import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

import config
from src.content.generator import GeneratedContent
from src.content.image_utils import load_font, wrap_text

logger = logging.getLogger(__name__)

PALETTE = {
    "bg_thumb": "#1A3C5E",
    "bg_body": "#F7F5F0",
    "accent": "#F0A500",
    "text_light": "#FFFFFF",
    "text_dark": "#1A1A2E",
    "text_sub": "#556",
}

TW = config.BLOG_THUMB_WIDTH
TH = config.BLOG_THUMB_HEIGHT
BW = config.BLOG_BODY_WIDTH
BH = config.BLOG_BODY_HEIGHT


def _thumbnail(title: str, date: str) -> Image.Image:
    img = Image.new("RGB", (TW, TH), PALETTE["bg_thumb"])
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, TW, 10], fill=PALETTE["accent"])
    draw.rectangle([0, TH - 10, TW, TH], fill=PALETTE["accent"])

    brand_font = load_font(34, bold=True)
    draw.text((70, 60), "Mr. Homes GA", font=brand_font, fill=PALETTE["accent"])

    sub_font = load_font(26)
    draw.text((70, 108), "관악구 부동산 뉴스 브리핑", font=sub_font, fill="#AACCEE")

    title_font = load_font(56, bold=True)
    wrapped = wrap_text(title, width=20)[:4]
    y = TH // 2 - (len(wrapped) * 70) // 2
    for line in wrapped:
        draw.text((70, y), line, font=title_font, fill=PALETTE["text_light"])
        y += 70

    date_font = load_font(28)
    draw.text((70, TH - 60), date, font=date_font, fill="#AACCEE")

    return img


def _body_image(index: int, quote: str) -> Image.Image:
    img = Image.new("RGB", (BW, BH), PALETTE["bg_body"])
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, BW, 12], fill=PALETTE["accent"])

    quote_font = load_font(48, bold=True)
    wrapped = wrap_text(quote, width=16)
    line_h = 66
    total_h = len(wrapped) * line_h
    y = (BH - total_h) // 2
    for line in wrapped:
        draw.text((BW // 2, y), line, font=quote_font, fill=PALETTE["text_dark"], anchor="mm")
        y += line_h

    brand_font = load_font(24)
    draw.text((BW // 2, BH - 50), "Mr. Homes GA | 관악구 부동산", font=brand_font, fill=PALETTE["text_sub"], anchor="mm")
    draw.rectangle([0, BH - 12, BW, BH], fill=PALETTE["accent"])
    return img


def create_blog_images(
    content: GeneratedContent, draft_id: Optional[str] = None, output_dir: Optional[Path] = None
) -> dict:
    """
    블로그 썸네일 + 본문 삽입 이미지를 생성해 저장.
    draft_id 로 저장 폴더를 구분한다 (미지정 시 content.date 로 폴백).
    반환: {"thumbnail": Path, "body_images": [Path, ...]}
    """
    out_dir = (output_dir or config.OUTPUT_DIR / "blog_images") / (draft_id or content.date)
    out_dir.mkdir(parents=True, exist_ok=True)

    result: dict = {"thumbnail": None, "body_images": []}

    if not content.blog_title:
        logger.warning("블로그 제목 없음 — 이미지 생성 건너뜀")
        return result

    thumb_path = out_dir / "thumbnail.jpg"
    _thumbnail(content.blog_title, content.date).save(thumb_path, "JPEG", quality=95)
    result["thumbnail"] = thumb_path
    logger.info("블로그 썸네일 생성 완료 → %s", thumb_path)

    for idx, quote in enumerate(content.highlight_quotes[:3], start=1):
        path = out_dir / f"body_{idx:02d}.jpg"
        _body_image(idx, quote).save(path, "JPEG", quality=95)
        result["body_images"].append(path)

    if result["body_images"]:
        logger.info("본문 삽입 이미지 %d장 생성 완료", len(result["body_images"]))

    return result

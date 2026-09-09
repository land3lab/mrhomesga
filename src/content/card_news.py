"""
Pillow를 이용한 카드뉴스 이미지 생성 (1080×1080 Instagram 정사각형).
"""

import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

import config
from src.content.generator import GeneratedContent
from src.content.image_utils import load_font, wrap_text

logger = logging.getLogger(__name__)

# 색상 팔레트
PALETTE = {
    "bg_cover":    "#1A3C5E",   # 표지 배경 (짙은 네이비)
    "bg_body":     "#FFFFFF",   # 본문 배경
    "bg_last":     "#F0A500",   # 마지막 슬라이드 배경 (골드)
    "accent":      "#F0A500",   # 강조색
    "text_light":  "#FFFFFF",
    "text_dark":   "#1A1A2E",
    "text_sub":    "#555555",
    "bar":         "#F0A500",
}

W = config.CARD_WIDTH
H = config.CARD_HEIGHT


def _draw_rounded_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill: str) -> None:
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def _slide_cover(title: str, date: str) -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["bg_cover"])
    draw = ImageDraw.Draw(img)

    # 상단 강조 바
    draw.rectangle([0, 0, W, 8], fill=PALETTE["bar"])

    # 로고/브랜드 텍스트
    brand_font = load_font(32, bold=True)
    draw.text((60, 50), "Mr. Homes GA", font=brand_font, fill=PALETTE["accent"])

    # 부제목
    sub_font = load_font(28)
    draw.text((60, 100), "관악구 부동산 뉴스 브리핑", font=sub_font, fill="#AACCEE")

    # 구분선
    draw.rectangle([60, 150, W - 60, 154], fill=PALETTE["bar"])

    # 메인 제목
    title_font = load_font(52, bold=True)
    wrapped = wrap_text(title, width=18)
    y = 220
    for line in wrapped:
        draw.text((60, y), line, font=title_font, fill=PALETTE["text_light"])
        y += 70

    # 날짜
    date_font = load_font(30)
    draw.text((60, H - 100), date, font=date_font, fill="#AACCEE")

    # 하단 강조 바
    draw.rectangle([0, H - 8, W, H], fill=PALETTE["bar"])
    return img


def _slide_body(index: int, slide_title: str, slide_body: str) -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["bg_body"])
    draw = ImageDraw.Draw(img)

    # 상단 색 바
    draw.rectangle([0, 0, W, 120], fill=PALETTE["bg_cover"])

    # 슬라이드 번호
    num_font = load_font(28, bold=True)
    draw.text((60, 40), f"{index:02d}", font=num_font, fill=PALETTE["accent"])

    # 슬라이드 제목
    title_font = load_font(38, bold=True)
    draw.text((60, 75), slide_title, font=title_font, fill=PALETTE["text_light"])

    # 하단 강조 바
    draw.rectangle([0, 118, W, 126], fill=PALETTE["bar"])

    # 본문 텍스트
    body_font = load_font(36)
    wrapped = wrap_text(slide_body, width=22)
    y = 200
    for line in wrapped:
        draw.text((60, y), line, font=body_font, fill=PALETTE["text_dark"])
        y += 58

    # 왼쪽 강조 세로선
    draw.rectangle([40, 200, 48, y], fill=PALETTE["accent"])

    # 하단 브랜드
    brand_font = load_font(24)
    draw.text((60, H - 60), "Mr. Homes GA | 관악구 부동산", font=brand_font, fill=PALETTE["text_sub"])
    draw.rectangle([0, H - 8, W, H], fill=PALETTE["bar"])
    return img


def _slide_cta(slide_title: str, slide_body: str) -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["bg_last"])
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W, 8], fill=PALETTE["bg_cover"])

    title_font = load_font(54, bold=True)
    wrapped = wrap_text(slide_title, width=14)
    y = 320
    for line in wrapped:
        draw.text((W // 2, y), line, font=title_font, fill=PALETTE["text_dark"], anchor="mm")
        y += 70

    body_font = load_font(34)
    bwrapped = wrap_text(slide_body, width=20)
    y += 30
    for line in bwrapped:
        draw.text((W // 2, y), line, font=body_font, fill=PALETTE["text_dark"], anchor="mm")
        y += 50

    brand_font = load_font(28, bold=True)
    draw.text((W // 2, H - 80), "Mr. Homes GA", font=brand_font, fill=PALETTE["bg_cover"], anchor="mm")
    draw.rectangle([0, H - 8, W, H], fill=PALETTE["bg_cover"])
    return img


def create_card_news(content: GeneratedContent, output_dir: Optional[Path] = None) -> list[Path]:
    """
    GeneratedContent의 card_slides를 이미지 파일로 저장.
    반환: 저장된 이미지 경로 리스트.
    """
    if not content.card_slides:
        logger.warning("카드뉴스 슬라이드 데이터 없음")
        return []

    out_dir = (output_dir or config.OUTPUT_DIR / "card_news") / content.date
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    slides = content.card_slides

    for idx, slide in enumerate(slides):
        title = slide.get("title", "")
        body = slide.get("body", "")

        if idx == 0:
            img = _slide_cover(content.blog_title, content.date)
        elif idx == len(slides) - 1:
            img = _slide_cta(title, body)
        else:
            img = _slide_body(idx, title, body)

        path = out_dir / f"slide_{idx + 1:02d}.jpg"
        img.save(path, "JPEG", quality=95)
        paths.append(path)
        logger.debug("슬라이드 저장: %s", path)

    logger.info("%d장 카드뉴스 생성 완료 → %s", len(paths), out_dir)
    return paths

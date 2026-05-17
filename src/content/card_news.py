"""
Pillow를 이용한 카드뉴스 이미지 생성 (1080×1080 Instagram 정사각형).
생성 후 HTML 미리보기 파일도 함께 출력한다.
"""

import logging
import textwrap
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

import config
from src.content.models import GeneratedContent

logger = logging.getLogger(__name__)

PALETTE = {
    "bg_cover":   "#1A3C5E",
    "bg_body":    "#FFFFFF",
    "bg_last":    "#F0A500",
    "accent":     "#F0A500",
    "text_light": "#FFFFFF",
    "text_dark":  "#1A1A2E",
    "text_sub":   "#666666",
    "bar":        "#F0A500",
    "tag_bg":     "#E8F0FE",
    "tag_text":   "#1A3C5E",
}

W = config.CARD_WIDTH
H = config.CARD_HEIGHT

_FONT_CACHE: dict[tuple, ImageFont.ImageFont] = {}


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf" if bold
        else "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold
        else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKkr-Bold.otf" if bold
        else "/usr/share/fonts/truetype/noto/NotoSansCJKkr-Regular.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    font: ImageFont.ImageFont = ImageFont.load_default()
    for path in candidates:
        if Path(path).exists():
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue
    _FONT_CACHE[key] = font
    return font


def _wrap_korean(text: str, max_chars: int) -> list[str]:
    """한글 기준 줄바꿈 (textwrap은 바이트가 아닌 문자 수로 처리)."""
    return textwrap.wrap(text, width=max_chars, break_long_words=True, break_on_hyphens=False)


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    font: ImageFont.ImageFont,
    fill: str,
    max_chars: int,
    line_spacing: int,
    max_lines: int = 10,
    anchor: str = "la",
) -> int:
    """여러 줄 텍스트를 그리고 마지막 y 좌표 반환."""
    lines = _wrap_korean(text, max_chars)[:max_lines]
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill, anchor=anchor)
        y += line_spacing
    return y


def _slide_cover(title: str, date: str, keyword_tags: list[str]) -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["bg_cover"])
    draw = ImageDraw.Draw(img)

    # 상단 강조 바
    draw.rectangle([0, 0, W, 10], fill=PALETTE["bar"])

    # 왼쪽 세로 강조선
    draw.rectangle([0, 10, 8, H - 10], fill=PALETTE["accent"])

    # 브랜드
    draw.text((70, 55), "Mr. Homes GA", font=_load_font(34, bold=True), fill=PALETTE["accent"])
    draw.text((70, 105), "관악구 부동산 뉴스 브리핑", font=_load_font(28), fill="#AACCEE")

    # 구분선
    draw.rectangle([70, 158, W - 70, 162], fill=PALETTE["bar"])

    # 메인 제목
    _draw_text_block(
        draw, title, 70, 200,
        font=_load_font(54, bold=True),
        fill=PALETTE["text_light"],
        max_chars=16, line_spacing=72, max_lines=4,
    )

    # 키워드 태그 (하단부)
    tag_y = H - 200
    tag_x = 70
    for tag in keyword_tags[:5]:
        tag_text = f"#{tag}"
        tf = _load_font(26)
        bbox = draw.textbbox((0, 0), tag_text, font=tf)
        tw = bbox[2] - bbox[0] + 20
        if tag_x + tw > W - 70:
            break
        draw.rounded_rectangle([tag_x, tag_y, tag_x + tw, tag_y + 38], radius=6, fill="#2A5C8E")
        draw.text((tag_x + 10, tag_y + 5), tag_text, font=tf, fill=PALETTE["accent"])
        tag_x += tw + 12

    # 날짜
    draw.text((70, H - 110), date, font=_load_font(30), fill="#AACCEE")

    # 하단 바
    draw.rectangle([0, H - 10, W, H], fill=PALETTE["bar"])
    return img


def _slide_body(index: int, slide_title: str, slide_body: str, total: int) -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["bg_body"])
    draw = ImageDraw.Draw(img)

    # 헤더 배경
    draw.rectangle([0, 0, W, 130], fill=PALETTE["bg_cover"])
    draw.rectangle([0, 128, W, 136], fill=PALETTE["bar"])

    # 슬라이드 번호 뱃지
    draw.ellipse([60, 30, 100, 70], fill=PALETTE["accent"])
    draw.text((80, 50), str(index), font=_load_font(26, bold=True), fill=PALETTE["text_dark"], anchor="mm")

    # 헤더 제목
    draw.text((120, 40), slide_title, font=_load_font(38, bold=True), fill=PALETTE["text_light"])

    # 왼쪽 강조 세로선 (본문 영역)
    draw.rectangle([60, 165, 68, H - 100], fill=PALETTE["accent"])

    # 본문 텍스트
    _draw_text_block(
        draw, slide_body, 90, 175,
        font=_load_font(36),
        fill=PALETTE["text_dark"],
        max_chars=20, line_spacing=62, max_lines=10,
    )

    # 진행 표시기 (하단)
    dot_total = total - 2  # 표지·마지막 슬라이드 제외
    if dot_total > 0:
        dot_y = H - 55
        dot_spacing = 22
        start_x = W // 2 - (dot_total * dot_spacing) // 2
        for i in range(dot_total):
            fill = PALETTE["accent"] if i + 1 == index else "#CCCCCC"
            draw.ellipse(
                [start_x + i * dot_spacing, dot_y,
                 start_x + i * dot_spacing + 12, dot_y + 12],
                fill=fill,
            )

    # 하단 브랜드
    draw.text((W - 60, H - 30), "Mr. Homes GA", font=_load_font(22), fill=PALETTE["text_sub"], anchor="rm")
    draw.rectangle([0, H - 10, W, H], fill=PALETTE["bar"])
    return img


def _slide_cta(slide_title: str, slide_body: str) -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["bg_last"])
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W, 10], fill=PALETTE["bg_cover"])

    # 중앙 아이콘 원
    cx = W // 2
    draw.ellipse([cx - 70, 240, cx + 70, 380], fill=PALETTE["bg_cover"])
    draw.text((cx, 310), "🏠", font=_load_font(54), fill=PALETTE["accent"], anchor="mm")

    # 제목
    y = 420
    for line in _wrap_korean(slide_title, 14)[:3]:
        draw.text((cx, y), line, font=_load_font(52, bold=True), fill=PALETTE["text_dark"], anchor="mm")
        y += 68

    # 본문
    y += 20
    for line in _wrap_korean(slide_body, 20)[:3]:
        draw.text((cx, y), line, font=_load_font(32), fill=PALETTE["text_dark"], anchor="mm")
        y += 48

    # 브랜드
    draw.text((cx, H - 80), "Mr. Homes GA", font=_load_font(30, bold=True), fill=PALETTE["bg_cover"], anchor="mm")
    draw.text((cx, H - 45), "관악구 부동산 전문", font=_load_font(24), fill=PALETTE["bg_cover"], anchor="mm")
    draw.rectangle([0, H - 10, W, H], fill=PALETTE["bg_cover"])
    return img


def create_card_news(content: GeneratedContent, output_dir: Optional[Path] = None) -> list[Path]:
    """
    GeneratedContent의 card_slides를 이미지 파일로 저장.
    HTML 미리보기 파일도 함께 생성.
    반환: 저장된 이미지 경로 리스트.
    """
    if not content.card_slides:
        logger.warning("카드뉴스 슬라이드 데이터 없음")
        return []

    out_dir = (output_dir or config.OUTPUT_DIR / "card_news") / content.date
    out_dir.mkdir(parents=True, exist_ok=True)

    # 키워드 태그 추출 (해시태그에서)
    keyword_tags = [t.lstrip("#") for t in content.hashtags[:6]] or ["관악구", "부동산", "아파트"]

    paths: list[Path] = []
    slides = content.card_slides
    total = len(slides)

    for idx, slide in enumerate(slides):
        title = slide.get("title", "")
        body = slide.get("body", "")

        if idx == 0:
            img = _slide_cover(content.blog_title, content.date, keyword_tags)
        elif idx == total - 1:
            img = _slide_cta(title, body)
        else:
            img = _slide_body(idx, title, body, total)

        path = out_dir / f"slide_{idx + 1:02d}.jpg"
        img.save(path, "JPEG", quality=95, optimize=True)
        paths.append(path)
        logger.debug("슬라이드 저장: %s", path)

    _generate_html_preview(content, paths, out_dir)
    logger.info("%d장 카드뉴스 생성 완료 → %s", len(paths), out_dir)
    return paths


def _generate_html_preview(content: GeneratedContent, image_paths: list[Path], out_dir: Path) -> None:
    """카드 이미지들을 보여주는 HTML 미리보기 파일 생성."""
    img_tags = "\n".join(
        f'<img src="{p.name}" alt="Slide {i+1}" loading="lazy">'
        for i, p in enumerate(image_paths)
    )
    hashtags_html = " ".join(
        f'<span class="tag">{h}</span>' for h in content.hashtags
    )

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{content.blog_title} — 카드뉴스 미리보기</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Apple SD Gothic Neo', '맑은 고딕', sans-serif;
          background: #f0f2f5; color: #1a1a2e; }}
  header {{ background: #1A3C5E; color: #fff; padding: 24px 40px; }}
  header h1 {{ font-size: 1.5rem; margin-bottom: 6px; }}
  header p {{ color: #AACCEE; font-size: 0.9rem; }}
  .slides {{ display: flex; flex-wrap: wrap; gap: 20px;
             padding: 32px 40px; justify-content: center; }}
  .slides img {{ width: 320px; height: 320px; object-fit: cover;
                 border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,.15);
                 transition: transform .2s; }}
  .slides img:hover {{ transform: scale(1.04); }}
  .caption {{ background: #fff; margin: 0 40px 24px;
              border-radius: 12px; padding: 24px 32px;
              box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
  .caption h2 {{ font-size: 1.1rem; margin-bottom: 12px; color: #1A3C5E; }}
  .caption p {{ white-space: pre-line; line-height: 1.7; font-size: 0.95rem; }}
  .tags {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
  .tag {{ background: #e8f0fe; color: #1A3C5E; padding: 4px 12px;
          border-radius: 20px; font-size: 0.82rem; }}
  footer {{ text-align: center; padding: 24px; color: #999; font-size: 0.8rem; }}
</style>
</head>
<body>
<header>
  <h1>{content.blog_title}</h1>
  <p>Mr. Homes GA — 카드뉴스 미리보기 | {content.date}</p>
</header>
<div class="slides">
{img_tags}
</div>
<div class="caption">
  <h2>인스타그램 캡션</h2>
  <p>{content.instagram_caption}</p>
  <div class="tags">{hashtags_html}</div>
</div>
<footer>생성일: {content.date} | Mr. Homes GA 자동 콘텐츠 시스템</footer>
</body>
</html>"""

    preview_path = out_dir / "preview.html"
    preview_path.write_text(html, encoding="utf-8")
    logger.info("HTML 미리보기 생성: %s", preview_path)

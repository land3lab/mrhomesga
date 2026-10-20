"""
블로그 발행 모듈
- Tistory API (OAuth2 access_token 방식)
- Naver Blog는 공식 포스팅 API 미제공 → Tistory 우선 지원
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

import config
from src.content.generator import GeneratedContent
from src.publishers.image_hosting import upload_to_imgbb

logger = logging.getLogger(__name__)

TISTORY_API = "https://www.tistory.com/apis"


def _embed_body_images(html: str, image_urls: list[str]) -> str:
    """본문 <p> 태그 사이에 이미지를 고르게 삽입."""
    if not image_urls:
        return html

    parts = html.split("</p>")
    n_paragraphs = max(len(parts) - 1, 1)
    interval = max(n_paragraphs // (len(image_urls) + 1), 1)

    result = []
    img_idx = 0
    for i, part in enumerate(parts):
        result.append(part)
        is_last = i == len(parts) - 1
        if not is_last:
            result.append("</p>")
        if img_idx < len(image_urls) and not is_last and (i + 1) % interval == 0:
            result.append(f'<p><img src="{image_urls[img_idx]}" alt="" style="max-width:100%;"></p>')
            img_idx += 1

    while img_idx < len(image_urls):
        result.append(f'<p><img src="{image_urls[img_idx]}" alt="" style="max-width:100%;"></p>')
        img_idx += 1

    return "".join(result)


class TistoryPublisher:
    def __init__(self):
        self.token = config.TISTORY_ACCESS_TOKEN
        self.blog = config.TISTORY_BLOG_NAME

    def _is_configured(self) -> bool:
        return bool(self.token and self.blog)

    def post(
        self,
        content: GeneratedContent,
        thumbnail: Optional[Path] = None,
        body_images: Optional[list[Path]] = None,
    ) -> dict:
        """
        Tistory에 블로그 포스트 발행 (썸네일 + 본문 이미지 삽입).
        반환: {"url": ..., "post_id": ...}
        """
        if not self._is_configured():
            logger.warning("Tistory 설정 없음 — 로컬 파일로 저장합니다.")
            return self._save_local(content, thumbnail, body_images)

        # 태그 조합
        tags = ",".join(
            t.lstrip("#") for t in content.hashtags[:10]
        )

        # 이미지 업로드 (Imgbb) — 미설정 시 이미지 없이 텍스트만 발행
        thumbnail_url = upload_to_imgbb(thumbnail) if thumbnail else None
        body_image_urls = [url for url in (upload_to_imgbb(p) for p in (body_images or [])) if url]

        html_body = content.blog_html
        if thumbnail_url:
            html_body = f'<p><img src="{thumbnail_url}" alt="{content.blog_title}" style="max-width:100%;"></p>\n' + html_body
        html_body = _embed_body_images(html_body, body_image_urls)

        # 출처 링크 섹션
        source_links = ""
        if content.source_articles:
            links = "\n".join(
                f'<li><a href="{a.link}" target="_blank">{a.title}</a></li>'
                for a in content.source_articles
            )
            source_links = f"<h3>참고 기사</h3><ul>{links}</ul>"

        html_body = html_body + "\n" + source_links

        params = {
            "access_token": self.token,
            "output": "json",
            "blogName": self.blog,
            "title": content.blog_title,
            "content": html_body,
            "visibility": "3",          # 3=공개
            "tag": tags,
        }

        try:
            resp = requests.post(f"{TISTORY_API}/post/write", data=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            post_id = data.get("tistory", {}).get("postId", "")
            url = f"https://{self.blog}.tistory.com/{post_id}"
            logger.info("Tistory 발행 완료: %s", url)
            return {"status": "ok", "url": url, "post_id": post_id}
        except Exception as exc:
            logger.error("Tistory 발행 실패: %s", exc)
            return self._save_local(content, thumbnail, body_images)

    def _save_local(
        self,
        content: GeneratedContent,
        thumbnail: Optional[Path] = None,
        body_images: Optional[list[Path]] = None,
    ) -> dict:
        """API 미설정/실패 시 로컬 HTML 파일로 저장 (담당자 검토·수동 업로드용)."""
        import os

        out_dir = config.OUTPUT_DIR / "blog"
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{content.date}_blog.html"
        path = out_dir / filename

        def _rel(p: Path) -> str:
            return os.path.relpath(p, out_dir)

        thumb_html = f'<p><img src="{_rel(thumbnail)}" alt="{content.blog_title}" style="max-width:100%;"></p>' if thumbnail else ""
        body_html = _embed_body_images(content.blog_html, [_rel(p) for p in (body_images or [])])

        full_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>{content.blog_title}</title>
</head>
<body>
  <h1>{content.blog_title}</h1>
  <p><em>{content.date}</em></p>
  {thumb_html}
  {body_html}
</body>
</html>"""
        path.write_text(full_html, encoding="utf-8")
        logger.info("로컬 저장: %s", path)
        return {"status": "ok", "url": str(path), "post_id": ""}

"""
블로그 발행 모듈
- Tistory API (OAuth2 access_token 방식)
- Naver Blog는 공식 포스팅 API 미제공 → Tistory 우선 지원
"""

import logging
from datetime import datetime
from pathlib import Path

import requests

import config
from src.content.generator import GeneratedContent

logger = logging.getLogger(__name__)

TISTORY_API = "https://www.tistory.com/apis"


class TistoryPublisher:
    def __init__(self):
        self.token = config.TISTORY_ACCESS_TOKEN
        self.blog = config.TISTORY_BLOG_NAME

    def _is_configured(self) -> bool:
        return bool(self.token and self.blog)

    def post(self, content: GeneratedContent) -> dict:
        """
        Tistory에 블로그 포스트 발행.
        반환: {"url": ..., "post_id": ...}
        """
        if not self._is_configured():
            logger.warning("Tistory 설정 없음 — 로컬 파일로 저장합니다.")
            return self._save_local(content)

        # 태그 조합
        tags = ",".join(
            t.lstrip("#") for t in content.hashtags[:10]
        )

        # 출처 링크 섹션
        source_links = ""
        if content.source_articles:
            links = "\n".join(
                f'<li><a href="{a.link}" target="_blank">{a.title}</a></li>'
                for a in content.source_articles
            )
            source_links = f"<h3>참고 기사</h3><ul>{links}</ul>"

        html_body = content.blog_html + "\n" + source_links

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
            return {"url": url, "post_id": post_id}
        except Exception as exc:
            logger.error("Tistory 발행 실패: %s", exc)
            return self._save_local(content)

    def _save_local(self, content: GeneratedContent) -> dict:
        """API 실패 시 로컬 HTML 파일로 저장."""
        out_dir = config.OUTPUT_DIR / "blog"
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{content.date}_blog.html"
        path = out_dir / filename

        full_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>{content.blog_title}</title>
</head>
<body>
  <h1>{content.blog_title}</h1>
  <p><em>{content.date}</em></p>
  {content.blog_html}
</body>
</html>"""
        path.write_text(full_html, encoding="utf-8")
        logger.info("로컬 저장: %s", path)
        return {"url": str(path), "post_id": ""}

"""
Facebook 페이지 발행 모듈 (Facebook Graph API)
- https://developers.facebook.com/docs/pages/publishing
- 로컬 이미지 파일을 직접 업로드(멀티파트) — 별도 이미지 호스팅 불필요
- 이미지 0장이면 텍스트 게시글, 1장 이상이면 다중 사진 게시글(attached_media)

※ 사전 조건:
  1. Facebook 페이지 관리 권한을 가진 Meta 앱
  2. pages_manage_posts, pages_read_engagement 권한
  3. 페이지 액세스 토큰(장기 토큰 권장) + 페이지 ID
"""

import logging
from pathlib import Path
from typing import Optional

import requests

import config
from src.content.generator import GeneratedContent, build_facebook_caption

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v21.0"


class FacebookPublisher:
    def __init__(self):
        self.token = config.FACEBOOK_PAGE_ACCESS_TOKEN
        self.page_id = config.FACEBOOK_PAGE_ID

    def _is_configured(self) -> bool:
        return bool(self.token and self.page_id)

    def _upload_unpublished_photo(self, image_path: Path) -> Optional[str]:
        """사진을 페이지 앨범에 비공개(unpublished)로 업로드 → media_fbid 반환."""
        with open(image_path, "rb") as f:
            resp = requests.post(
                f"{GRAPH_API}/{self.page_id}/photos",
                data={"published": "false", "access_token": self.token},
                files={"source": f},
                timeout=30,
            )
        resp.raise_for_status()
        return resp.json().get("id")

    def post(self, image_paths: list[Path], content: GeneratedContent) -> dict:
        """이미지(0장 이상) + 캡션으로 페이지 게시글 작성."""
        if not self._is_configured():
            logger.warning("Facebook 설정 없음 — 건너뜁니다.")
            return {"status": "skipped", "reason": "Facebook 미설정"}

        caption = build_facebook_caption(content)

        try:
            if not image_paths:
                resp = requests.post(
                    f"{GRAPH_API}/{self.page_id}/feed",
                    data={"message": caption, "access_token": self.token},
                    timeout=30,
                )
                resp.raise_for_status()
                post_id = resp.json().get("id")
            elif len(image_paths) == 1:
                with open(image_paths[0], "rb") as f:
                    resp = requests.post(
                        f"{GRAPH_API}/{self.page_id}/photos",
                        data={"caption": caption, "access_token": self.token},
                        files={"source": f},
                        timeout=30,
                    )
                resp.raise_for_status()
                post_id = resp.json().get("post_id") or resp.json().get("id")
            else:
                media_ids = []
                for path in image_paths[:10]:
                    fbid = self._upload_unpublished_photo(path)
                    if fbid:
                        media_ids.append(fbid)

                if not media_ids:
                    return {"status": "failed", "reason": "사진 업로드 실패"}

                params: dict = {"message": caption, "access_token": self.token}
                for idx, fbid in enumerate(media_ids):
                    params[f"attached_media[{idx}]"] = f'{{"media_fbid":"{fbid}"}}'

                resp = requests.post(f"{GRAPH_API}/{self.page_id}/feed", data=params, timeout=30)
                resp.raise_for_status()
                post_id = resp.json().get("id")

            logger.info("Facebook 발행 완료: %s", post_id)
            return {"status": "ok", "post_id": post_id}

        except Exception as exc:
            logger.error("Facebook 발행 실패: %s", exc)
            return {"status": "failed", "reason": str(exc)}

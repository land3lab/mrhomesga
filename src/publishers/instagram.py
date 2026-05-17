"""
Instagram 발행 모듈
- Instagram Graph API (공식) — 비즈니스/크리에이터 계정 전용
- 카드뉴스 Carousel 또는 단일 이미지 포스팅

※ 사전 조건:
  1. Facebook Business Manager에서 Meta 앱 생성
  2. Instagram Graph API 권한 (instagram_content_publish, instagram_manage_insights)
  3. 이미지는 공개 접근 가능한 URL 필요 → 로컬 파일은 임시 호스팅 서버 또는 Imgbb/S3 필요
"""

import logging
import time
from pathlib import Path
from typing import Optional

import requests

import config
from src.content.models import GeneratedContent
from src.content.generator import build_instagram_caption

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v21.0"

# 이미지 공개 호스팅이 없는 환경을 위한 무료 Imgbb API (선택적)
# IMGBB_API_KEY 환경변수로 설정하면 자동으로 업로드 후 URL 획득
import os
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")
IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"


def _upload_to_imgbb(image_path: Path) -> Optional[str]:
    """로컬 이미지를 Imgbb에 업로드하고 공개 URL 반환."""
    if not IMGBB_API_KEY:
        return None
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                IMGBB_UPLOAD_URL,
                data={"key": IMGBB_API_KEY},
                files={"image": f},
                timeout=30,
            )
        resp.raise_for_status()
        return resp.json()["data"]["url"]
    except Exception as exc:
        logger.warning("Imgbb 업로드 실패 (%s): %s", image_path.name, exc)
        return None


class InstagramPublisher:
    def __init__(self):
        self.token = config.INSTAGRAM_ACCESS_TOKEN
        self.account_id = config.INSTAGRAM_ACCOUNT_ID

    def _is_configured(self) -> bool:
        return bool(self.token and self.account_id)

    def _create_media_container(self, image_url: str, caption: str = "", is_carousel_item: bool = False) -> Optional[str]:
        """미디어 컨테이너 생성 → container_id 반환."""
        params: dict = {
            "image_url": image_url,
            "access_token": self.token,
        }
        if is_carousel_item:
            params["is_carousel_item"] = "true"
        else:
            params["caption"] = caption

        resp = requests.post(
            f"{GRAPH_API}/{self.account_id}/media",
            data=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("id")

    def _create_carousel_container(self, children: list[str], caption: str) -> Optional[str]:
        """카루셀 컨테이너 생성."""
        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
            "access_token": self.token,
        }
        resp = requests.post(
            f"{GRAPH_API}/{self.account_id}/media",
            data=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("id")

    def _publish_container(self, container_id: str) -> Optional[str]:
        """컨테이너 발행 → 게시물 ID 반환."""
        params = {
            "creation_id": container_id,
            "access_token": self.token,
        }
        resp = requests.post(
            f"{GRAPH_API}/{self.account_id}/media_publish",
            data=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("id")

    def post_carousel(self, image_paths: list[Path], content: GeneratedContent) -> dict:
        """카드뉴스 이미지들을 Instagram Carousel로 발행."""
        if not self._is_configured():
            logger.warning("Instagram 설정 없음 — 건너뜁니다.")
            return {"status": "skipped", "reason": "Instagram 미설정"}

        caption = build_instagram_caption(content)

        # 이미지 URL 목록 수집
        image_urls: list[str] = []
        for path in image_paths[:10]:  # Instagram 최대 10장
            url = _upload_to_imgbb(path)
            if url:
                image_urls.append(url)
            else:
                logger.warning("URL 없음 — %s 건너뜀", path.name)

        if not image_urls:
            return {"status": "failed", "reason": "이미지 URL 없음 (IMGBB_API_KEY 필요)"}

        try:
            if len(image_urls) == 1:
                # 단일 이미지
                container_id = self._create_media_container(image_urls[0], caption=caption)
            else:
                # 카루셀
                children = []
                for url in image_urls:
                    cid = self._create_media_container(url, is_carousel_item=True)
                    if cid:
                        children.append(cid)
                    time.sleep(0.5)  # API 속도 제한 방지
                container_id = self._create_carousel_container(children, caption)

            if not container_id:
                return {"status": "failed", "reason": "컨테이너 생성 실패"}

            # 최대 60초 대기 (처리 완료 대기)
            time.sleep(5)
            post_id = self._publish_container(container_id)
            post_url = f"https://www.instagram.com/p/{post_id}/" if post_id else ""
            logger.info("Instagram 발행 완료: %s", post_url)
            return {"status": "ok", "post_id": post_id, "url": post_url}

        except Exception as exc:
            logger.error("Instagram 발행 실패: %s", exc)
            return {"status": "failed", "reason": str(exc)}

    def post_single(self, image_path: Path, content: GeneratedContent) -> dict:
        """단일 이미지 발행 (표지 슬라이드)."""
        return self.post_carousel([image_path], content)

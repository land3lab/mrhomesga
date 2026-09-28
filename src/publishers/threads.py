"""
Threads 발행 모듈 (Meta Threads API)
- https://developers.facebook.com/docs/threads
- 텍스트 단독, 단일 이미지, 또는 캐러셀(최대 10장) 게시 지원

※ 사전 조건:
  1. Meta 개발자 계정 + Threads API 사용 앱 등록
  2. threads_basic, threads_content_publish 권한
  3. 이미지는 공개 접근 가능한 URL 필요 → IMGBB_API_KEY로 자동 호스팅
"""

import logging
import time
from pathlib import Path
from typing import Optional

import requests

import config
from src.content.generator import GeneratedContent, build_threads_caption
from src.publishers.image_hosting import upload_to_imgbb

logger = logging.getLogger(__name__)

THREADS_API = "https://graph.threads.net/v1.0"


class ThreadsPublisher:
    def __init__(self):
        self.token = config.THREADS_ACCESS_TOKEN
        self.user_id = config.THREADS_USER_ID

    def _is_configured(self) -> bool:
        return bool(self.token and self.user_id)

    def _create_container(self, params: dict) -> Optional[str]:
        params = {**params, "access_token": self.token}
        resp = requests.post(f"{THREADS_API}/{self.user_id}/threads", data=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("id")

    def _publish_container(self, container_id: str) -> Optional[str]:
        params = {"creation_id": container_id, "access_token": self.token}
        resp = requests.post(f"{THREADS_API}/{self.user_id}/threads_publish", data=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("id")

    def post(self, image_paths: list[Path], content: GeneratedContent) -> dict:
        """카드뉴스 이미지(0~10장) + 캡션으로 쓰레드 게시."""
        if not self._is_configured():
            logger.warning("Threads 설정 없음 — 건너뜁니다.")
            return {"status": "skipped", "reason": "Threads 미설정"}

        caption = build_threads_caption(content)

        try:
            if not image_paths:
                container_id = self._create_container({"media_type": "TEXT", "text": caption})
            else:
                image_urls = [url for url in (upload_to_imgbb(p) for p in image_paths[:10]) if url]
                if not image_urls:
                    return {"status": "failed", "reason": "이미지 URL 없음 (IMGBB_API_KEY 필요)"}

                if len(image_urls) == 1:
                    container_id = self._create_container({
                        "media_type": "IMAGE",
                        "image_url": image_urls[0],
                        "text": caption,
                    })
                else:
                    children = []
                    for url in image_urls:
                        cid = self._create_container({
                            "media_type": "IMAGE",
                            "image_url": url,
                            "is_carousel_item": "true",
                        })
                        if cid:
                            children.append(cid)
                        time.sleep(0.5)
                    container_id = self._create_container({
                        "media_type": "CAROUSEL",
                        "children": ",".join(children),
                        "text": caption,
                    })

            if not container_id:
                return {"status": "failed", "reason": "컨테이너 생성 실패"}

            time.sleep(5)  # Threads 처리 대기 (공식 가이드 권장)
            post_id = self._publish_container(container_id)
            logger.info("Threads 발행 완료: %s", post_id)
            return {"status": "ok", "post_id": post_id}

        except Exception as exc:
            logger.error("Threads 발행 실패: %s", exc)
            return {"status": "failed", "reason": str(exc)}

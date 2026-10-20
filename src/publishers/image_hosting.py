"""
로컬 이미지를 공개 URL로 호스팅하는 공통 헬퍼.
Instagram / Threads / Facebook / 블로그 이미지 발행 시 공통으로 사용.

Imgbb(https://imgbb.com/api) 무료 API를 사용 — IMGBB_API_KEY 환경변수 필요.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")
IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"


def upload_to_imgbb(image_path: Path) -> Optional[str]:
    """로컬 이미지를 Imgbb에 업로드하고 공개 URL 반환. 미설정/실패 시 None."""
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

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
from fastapi import HTTPException, UploadFile
from loguru import logger
from PIL import Image, ImageOps

from ..core.supabase import SupabaseStorageHelper, supabase_storage

# Giới hạn decode ảnh upload để chống decompression-bomb / OOM.
MAX_IMAGE_PIXELS = 12_000_000  # ~12MP
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def decode_image_bytes(content: bytes) -> np.ndarray:
    """Decode bytes ảnh -> BGR uint8 (OpenCV-ready), xử lý EXIF orientation.

    Một cổng duy nhất thay các chỗ `cv2.imdecode` rải rác (files.py, storage).
    Pillow tự validate định dạng + EXIF; BGR giữ nguyên quy ước OpenCV.
    """
    try:
        with Image.open(BytesIO(content)) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            if im.width * im.height > MAX_IMAGE_PIXELS:
                raise ValueError("ảnh quá lớn")
            rgb = np.asarray(im, dtype=np.uint8)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"File ảnh lỗi hoặc không đọc được: {e}")
    return rgb[:, :, ::-1].copy()  # RGB -> BGR


async def decode_upload(photo: UploadFile) -> np.ndarray:
    content = await photo.read()
    if not content:
        raise HTTPException(422, "File ảnh rỗng")
    return decode_image_bytes(content)


def encode_jpeg(img_bgr: np.ndarray, quality: int = 85) -> bytes:
    """Encode BGR array -> JPEG bytes bằng Pillow (thay cv2.imencode rải rác)."""
    rgb = img_bgr[:, :, ::-1]
    buf = BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=int(quality))
    return buf.getvalue()


def resolve_avatar_url(avatar_url: str | None, student_code: str) -> str | None:
    """Avatar DB -> fallback file local `/static/storage/avatars/<code>.jpg`."""
    if avatar_url:
        return avatar_url
    try:
        local_file: Path = (
            supabase_storage.storage_dir / SupabaseStorageHelper.BUCKET_AVATARS / f"{student_code}.jpg"
        )
    except Exception:  # noqa: BLE001
        return None
    if local_file.exists():
        return f"/static/storage/{SupabaseStorageHelper.BUCKET_AVATARS}/{student_code}.jpg"
    return None


async def upload_avatar_image(user_code: str, img_bgr: np.ndarray) -> str | None:
    """Upload ảnh chân dung (JPEG quality 85, upsert theo user_code).

    Trả None khi lỗi (ảnh chỉ để hiển thị).
    """
    try:
        content = encode_jpeg(img_bgr, quality=85)
        return await supabase_storage.upload_file(
            bucket=SupabaseStorageHelper.BUCKET_AVATARS,
            path=f"{user_code}.jpg",
            content=content,
            content_type="image/jpeg",
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Lỗi upload ảnh chân dung cho {user_code}: {e}")
        return None

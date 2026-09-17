from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, UploadFile, status
from loguru import logger

from ..core.supabase import SupabaseStorageHelper, supabase_storage

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


async def upload_leave_proof(file: Optional[UploadFile]) -> Optional[str]:
    """
    Upload file minh chứng xin nghỉ phép lên Supabase Storage (hoặc local fallback).

    - Kiểm tra MIME types (image/jpeg, image/png, application/pdf) -> 422 nếu sai.
    - Kiểm tra kích thước <= 5MB -> 422 nếu vượt quá.
    - Tạo tên file duy nhất (UUID + timestamp + extension).
    - Trả về URL của file sau khi upload thành công.
    """
    if file is None or not file.filename:
        return None

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Định dạng file '{file.content_type}' không hợp lệ. "
                "Chỉ chấp nhận image/jpeg, image/png hoặc application/pdf."
            ),
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kích thước file vượt quá giới hạn tối đa cho phép (5MB).",
        )

    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
        ext_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "application/pdf": ".pdf",
        }
        ext = ext_map.get(file.content_type, ".jpg")

    unique_filename = f"{uuid.uuid4().hex}_{int(time.time())}{ext}"

    try:
        url = await supabase_storage.upload_file(
            bucket=SupabaseStorageHelper.BUCKET_LEAVE_PROOFS,
            path=unique_filename,
            content=content,
            content_type=file.content_type,
        )
        return url
    except Exception as e:
        logger.error(f"Lỗi khi upload minh chứng nghỉ phép: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tải file minh chứng lên hệ thống lưu trữ.",
        )

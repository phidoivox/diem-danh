from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from loguru import logger

from .supabase import SupabaseStorageHelper, supabase_storage

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

__all__ = [
    "ALLOWED_MIME_TYPES",
    "MAX_FILE_SIZE_BYTES",
    "build_leave_proof_path",
    "upload_leave_proof",
    "upload_leave_proof_bytes",
    "validate_leave_proof_bytes",
]


def validate_leave_proof_bytes(data: bytes, content_type: Optional[str]) -> None:
    """Validate MIME + kích thước, raise 422."""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Định dạng file '{content_type}' không hợp lệ. "
                "Chỉ chấp nhận image/jpeg, image/png hoặc application/pdf."
            ),
        )
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Kích thước file vượt quá giới hạn tối đa cho phép (5MB).",
        )


def build_leave_proof_path(filename: Optional[str], content_type: Optional[str]) -> str:
    """Đặt tên file duy nhất UUID + timestamp + extension."""
    ext = Path(filename).suffix.lower() if filename else ""
    if ext not in [".jpg", ".jpeg", ".png", ".pdf"]:
        ext_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "application/pdf": ".pdf",
        }
        ext = ext_map.get(content_type or "", ".jpg")
    return f"{uuid.uuid4().hex}_{int(time.time())}{ext}"


async def upload_leave_proof_bytes(
    data: Optional[bytes],
    content_type: Optional[str],
    filename: Optional[str],
) -> Optional[str]:
    """Upload minh chứng từ bytes (route đã đọc UploadFile -> bytes ở biên).

    Trả None khi không có file (data rỗng + filename rỗng) — giữ nguyên ngữ
    nghĩa upload_leave_proof cũ.
    """
    if not data or not filename:
        return None

    validate_leave_proof_bytes(data, content_type)
    path = build_leave_proof_path(filename, content_type)
    try:
        return await supabase_storage.upload_file(
            bucket=SupabaseStorageHelper.BUCKET_LEAVE_PROOFS,
            path=path,
            content=data,
            content_type=content_type or "application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Lỗi khi upload minh chứng nghỉ phép: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tải file minh chứng lên hệ thống lưu trữ.",
        )


async def upload_leave_proof(file: Optional[UploadFile]) -> Optional[str]:
    """Upload file minh chứng (wrapper tương thích ngược).

    Đọc bytes tại đây rồi ủy thác cho upload_leave_proof_bytes cùng module
    (validate jpeg/png/pdf 5MB + UUID một mối tại đây).
    """
    if file is None or not file.filename:
        return None

    content = await file.read()
    return await upload_leave_proof_bytes(content, file.content_type, file.filename)

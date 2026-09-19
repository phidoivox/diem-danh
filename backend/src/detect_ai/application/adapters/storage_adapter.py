"""Storage adapter (Task 7).

Biên routes chuyển UploadFile -> bytes rồi gọi port. Giữ nguyên validate
jpeg/png/pdf 5MB + đặt tên UUID như storage_service hiện tại — chỉ đổi chỗ
đọc bytes ra biên (route) để application/core không dính FastAPI UploadFile.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from loguru import logger

from ...core.supabase import SupabaseStorageHelper, supabase_storage
from ..ports.repositories import StoragePort

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class SupabaseStorageAdapter:
    """Triển khai StoragePort bằng Supabase Storage (fallback đĩa local)."""

    def __init__(self, bucket: str = SupabaseStorageHelper.BUCKET_LEAVE_PROOFS):
        self.bucket = bucket

    async def upload(self, data: bytes, content_type: str, path: str) -> str:
        return await supabase_storage.upload_file(
            bucket=self.bucket,
            path=path,
            content=data,
            content_type=content_type,
        )


default_storage_port: StoragePort = SupabaseStorageAdapter()


def validate_leave_proof_bytes(data: bytes, content_type: Optional[str]) -> None:
    """Validate MIME + kích thước, raise 422 với message như storage_service cũ."""
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
    """Đặt tên file duy nhất UUID + timestamp + extension (như cũ)."""
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
    port: StoragePort | None = None,
) -> Optional[str]:
    """Upload minh chứng từ bytes (route đã đọc UploadFile -> bytes ở biên).

    Trả None khi không có file (data rỗng + filename rỗng) — giữ nguyên ngữ
    nghĩa upload_leave_proof cũ.
    """
    if not data or not filename:
        return None

    validate_leave_proof_bytes(data, content_type)
    path = build_leave_proof_path(filename, content_type)
    active_port = port or default_storage_port
    try:
        return await active_port.upload(data, content_type or "application/octet-stream", path)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Lỗi khi upload minh chứng nghỉ phép: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tải file minh chứng lên hệ thống lưu trữ.",
        )

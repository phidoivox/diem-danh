from __future__ import annotations

from typing import Optional

import numpy as np
from fastapi import UploadFile

from ..application.adapters.storage_adapter import (
    ALLOWED_MIME_TYPES as _ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES as _MAX_FILE_SIZE_BYTES,
    upload_leave_proof_bytes,
)

ALLOWED_MIME_TYPES = _ALLOWED_MIME_TYPES

MAX_FILE_SIZE_BYTES = _MAX_FILE_SIZE_BYTES


async def upload_leave_proof(file: Optional[UploadFile]) -> Optional[str]:
    """Upload file minh chứng (wrapper tương thích ngược).

    Biên mới đọc UploadFile -> bytes ở routes rồi gọi port; hàm này giữ lại
    cho code/tests cũ: đọc bytes tại đây rồi ủy thác cho adapter (validate
    jpeg/png/pdf 5MB + UUID giữ nguyên một mối trong adapter).
    """
    if file is None or not file.filename:
        return None

    content = await file.read()
    return await upload_leave_proof_bytes(content, file.content_type, file.filename)


async def upload_avatar(user_code: str, img: np.ndarray) -> Optional[str]:
    """Upload ảnh chân dung lên bucket avatars và trả URL công khai.

    Ảnh được mã hoá JPEG (quality 85) trước khi upload — ảnh gốc từ điện thoại
    thường là PNG/JPEG vài MB, không cần thiết cho một ảnh đại diện.

    Trả None nếu upload thất bại (ảnh chỉ để hiển thị).
    """
    from .image_service import upload_avatar_image

    return await upload_avatar_image(user_code, img)

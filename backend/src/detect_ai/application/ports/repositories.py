"""Hexagonal ports (Task 7).

StoragePort: biên lưu file trừu tượng — adapter Supabase/local triển khai,
phía gọi chỉ truyền bytes đã đọc ở biên (routes chuyển UploadFile -> bytes).
"""

from __future__ import annotations

from typing import Protocol


class StoragePort(Protocol):
    async def upload(self, data: bytes, content_type: str, path: str) -> str:
        """Upload bytes lên storage tại `path`, trả về URL công khai."""
        ...

"""Chuẩn hoá URL file riêng tư trả về cho client (dùng chung teacher/student).

DB cũ + code ghi snapshot lưu `/static/storage/snapshots/<sid>/<f>` — static
đó không còn mount (chỉ avatars được public). Hàm này rewrite sang
`/api/v1/files/snapshot/<sid>/<f>` (auth) để ảnh cũ vẫn xem được.
URL mới giữ nguyên.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlsplit

_LEGACY_SNAP_PREFIX = "/static/storage/snapshots/"
_LEGACY_AVATAR_PREFIX = "/static/storage/avatars/"


def _tail_after(url: str, prefix: str) -> str | None:
    """Trả phần sau prefix khi prefix nằm ở ĐẦU path (không phải query param)."""
    path = urlsplit(url).path if "://" in url else url.split("?", 1)[0]
    if path.startswith(prefix):
        return path[len(prefix):].lstrip("/")
    return None


def public_snapshot(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    tail = _tail_after(url, _LEGACY_SNAP_PREFIX)
    if tail is not None:
        return f"/api/v1/files/snapshot/{tail}"
    tail = _tail_after(url, _LEGACY_AVATAR_PREFIX)
    if tail is not None:
        return "/api/v1/files/avatar/" + tail
    return url

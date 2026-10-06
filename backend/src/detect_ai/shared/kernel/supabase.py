from __future__ import annotations

"""Lưu trữ file cục bộ (local-only).

Ảnh minh chứng/avatar/snapshot ghi xuống đĩa và phục vụ qua
`/api/v1/files/...` (auth). Chỉ đĩa local, không cloud.
"""

from pathlib import Path

from .config import DATA_DIR

STORAGE_DIR = DATA_DIR / "storage"


class SupabaseStorageHelper:
    """Ghi/đọc/xóa file trên đĩa local (giữ tên class cũ để khỏi sửa callers)."""

    BUCKET_LEAVE_PROOFS = "leave-proofs"
    BUCKET_AVATARS = "avatars"
    BUCKET_SNAPSHOTS = "snapshots"

    _URL_PREFIX = {
        BUCKET_LEAVE_PROOFS: "/api/v1/files/leave-proof",
        BUCKET_AVATARS: "/api/v1/files/avatar",
        BUCKET_SNAPSHOTS: "/api/v1/files/snapshot",
    }

    def __init__(self, storage_dir: Path = STORAGE_DIR, **_ignored) -> None:
        self.storage_dir = Path(storage_dir)
        for b in (self.BUCKET_LEAVE_PROOFS, self.BUCKET_AVATARS, self.BUCKET_SNAPSHOTS):
            (self.storage_dir / b).mkdir(parents=True, exist_ok=True)

    def _local_path(self, bucket: str, path: str) -> Path:
        return self.storage_dir / bucket / path.lstrip("/")

    async def upload_file(
        self,
        bucket: str,
        path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Ghi file xuống đĩa và trả về URL phục vụ qua API files."""
        clean_path = path.lstrip("/")
        local_file = self._local_path(bucket, clean_path)
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_bytes(content)
        return await self.get_public_url(bucket, clean_path)

    async def get_public_url(self, bucket: str, path: str) -> str:
        clean_path = path.lstrip("/")
        prefix = self._URL_PREFIX.get(bucket, f"/api/v1/files/{bucket}")
        return f"{prefix}/{clean_path}"

    async def delete_file(self, bucket: str, path: str) -> bool:
        local_file = self._local_path(bucket, path.lstrip("/"))
        if local_file.exists():
            local_file.unlink()
            return True
        return False


supabase_storage = SupabaseStorageHelper()

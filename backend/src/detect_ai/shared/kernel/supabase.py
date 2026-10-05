from __future__ import annotations

from pathlib import Path

from .config import DATA_DIR

STORAGE_DIR = DATA_DIR / "storage"
# Avatar riêng tư (đọc qua /api/v1/files/avatar, cần auth).
AVATAR_DIR = STORAGE_DIR / "avatars"


class SupabaseStorageHelper:
    """Lưu file ảnh/tài liệu xuống đĩa local, không upload cloud.

    - avatars: riêng tư, đọc qua /api/v1/files/avatar (auth).
    - leave-proofs / snapshots: riêng tư, đọc qua /api/v1/files (auth).

    Giữ nguyên tên module/class để các import hiện có không phải sửa.
    """

    BUCKET_LEAVE_PROOFS = "leave-proofs"
    BUCKET_AVATARS = "avatars"

    def __init__(self, storage_dir: Path = STORAGE_DIR, **_ignored):
        # **_ignored: chịu kwarg cũ để call-site và test cũ không vỡ
        # khi chuyển sang local-only.
        self.storage_dir = Path(storage_dir)

        for b in (self.BUCKET_LEAVE_PROOFS, self.BUCKET_AVATARS):
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
        """Ghi file xuống đĩa local và trả về URL đọc file."""
        clean_path = path.lstrip("/")

        local_file = self._local_path(bucket, clean_path)
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_bytes(content)

        return await self.get_public_url(bucket, clean_path)

    async def get_public_url(self, bucket: str, path: str) -> str:
        """URL đọc file local qua /api/v1/files (auth, không gắn <img> trần)."""
        clean_path = path.lstrip("/")
        if bucket == self.BUCKET_AVATARS:
            return f"/api/v1/files/avatar/{clean_path}"
        if bucket == self.BUCKET_LEAVE_PROOFS:
            return f"/api/v1/files/leave-proof/{clean_path}"
        return f"/api/v1/files/snapshot/{clean_path}"

    async def delete_file(self, bucket: str, path: str) -> bool:
        clean_path = path.lstrip("/")

        local_file = self._local_path(bucket, clean_path)
        if local_file.exists():
            local_file.unlink()
            return True
        return False


supabase_storage = SupabaseStorageHelper()

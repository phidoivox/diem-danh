from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    import storage3  # ponytail: guard — base requires storage3; env moved local-only (drift-supabase.patch), Task 9 resolves
    from storage3 import AsyncStorageClient, create_client
except ImportError:  # pragma: no cover
    storage3 = None
    AsyncStorageClient = None  # type: ignore[assignment,misc]
    create_client = None  # type: ignore[assignment]

from .config import DATA_DIR, SUPABASE_SERVICE_KEY, SUPABASE_URL

STORAGE_DIR = DATA_DIR / "storage"


class SupabaseStorageHelper:
    """Quản lý file trên Supabase Storage (bucket public), fallback xuống đĩa local.

    Dùng client chính thức `storage3` (module Storage của supabase-py) thay cho việc
    tự ghép URL/header REST thủ công. Fallback đĩa local được giữ nguyên để chạy
    dev/test khi chưa cấu hình Supabase.
    """

    BUCKET_LEAVE_PROOFS = "leave-proofs"
    BUCKET_AVATARS = "avatars"
    BUCKET_SNAPSHOTS = "snapshots"

    def __init__(
        self,
        supabase_url: str = SUPABASE_URL,
        service_key: str = SUPABASE_SERVICE_KEY,
        storage_dir: Path = STORAGE_DIR,
    ):
        self.supabase_url = supabase_url.rstrip("/") if supabase_url else ""
        self.service_key = service_key or ""
        self.storage_dir = Path(storage_dir)
        self._client: Optional[AsyncStorageClient] = None

        # Tạo sẵn thư mục cho 3 bucket (chỉ dùng ở chế độ fallback offline)
        for b in (self.BUCKET_LEAVE_PROOFS, self.BUCKET_AVATARS, self.BUCKET_SNAPSHOTS):
            (self.storage_dir / b).mkdir(parents=True, exist_ok=True)

    @property
    def is_cloud_enabled(self) -> bool:
        return bool(self.supabase_url and self.service_key)

    @property
    def client(self) -> AsyncStorageClient:
        """Khởi tạo một lần rồi tái sử dụng để giữ connection pool của httpx."""
        if self._client is None:
            self._client = create_client(
                f"{self.supabase_url}/storage/v1/",  # storage3 yêu cầu URL kết thúc bằng "/"
                {
                    "apikey": self.service_key,
                    "Authorization": f"Bearer {self.service_key}",
                },
                is_async=True,
            )
        return self._client

    def _local_path(self, bucket: str, path: str) -> Path:
        return self.storage_dir / bucket / path.lstrip("/")

    async def upload_file(
        self,
        bucket: str,
        path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload file lên bucket và trả về URL công khai của file."""
        clean_path = path.lstrip("/")

        if self.is_cloud_enabled:
            await self.client.from_(bucket).upload(
                clean_path,
                content,
                {"content-type": content_type, "upsert": "true"},
            )
        else:
            local_file = self._local_path(bucket, clean_path)
            local_file.parent.mkdir(parents=True, exist_ok=True)
            local_file.write_bytes(content)

        return await self.get_public_url(bucket, clean_path)

    async def get_public_url(self, bucket: str, path: str) -> str:
        clean_path = path.lstrip("/")
        if self.is_cloud_enabled:
            return await self.client.from_(bucket).get_public_url(clean_path)
        return f"/static/storage/{bucket}/{clean_path}"

    async def delete_file(self, bucket: str, path: str) -> bool:
        clean_path = path.lstrip("/")

        if self.is_cloud_enabled:
            removed = await self.client.from_(bucket).remove([clean_path])
            return bool(removed)

        local_file = self._local_path(bucket, clean_path)
        if local_file.exists():
            local_file.unlink()
            return True
        return False


supabase_storage = SupabaseStorageHelper()

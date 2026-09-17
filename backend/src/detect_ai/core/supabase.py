from __future__ import annotations
from pathlib import Path
import httpx
from loguru import logger
from .config import SUPABASE_URL, SUPABASE_SERVICE_KEY, DATA_DIR

STORAGE_DIR = DATA_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)


class SupabaseStorageHelper:
    """Helper for managing files in Supabase Storage buckets or local fallback."""

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
        self.service_key = service_key
        self.storage_dir = storage_dir
        # Ensure local bucket dirs exist
        for b in [self.BUCKET_LEAVE_PROOFS, self.BUCKET_AVATARS, self.BUCKET_SNAPSHOTS]:
            (self.storage_dir / b).mkdir(parents=True, exist_ok=True)

    @property
    def is_cloud_enabled(self) -> bool:
        return bool(self.supabase_url and self.service_key)

    async def upload_file(
        self,
        bucket: str,
        path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload file to bucket and return its public URL."""
        clean_path = path.lstrip("/")
        if self.is_cloud_enabled:
            url = f"{self.supabase_url}/storage/v1/object/{bucket}/{clean_path}"
            headers = {
                "Authorization": f"Bearer {self.service_key}",
                "Content-Type": content_type,
                "x-upsert": "true",
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, content=content, headers=headers)
                if resp.status_code not in (200, 201):
                    logger.error(f"Failed to upload to Supabase Storage: {resp.status_code} {resp.text}")
                    raise RuntimeError(f"Supabase storage upload failed: {resp.status_code}")
            return self.get_public_url(bucket, clean_path)
        else:
            # Fallback local disk
            local_file = self.storage_dir / bucket / clean_path
            local_file.parent.mkdir(parents=True, exist_ok=True)
            local_file.write_bytes(content)
            return f"/static/storage/{bucket}/{clean_path}"

    def get_public_url(self, bucket: str, path: str) -> str:
        clean_path = path.lstrip("/")
        if self.is_cloud_enabled:
            return f"{self.supabase_url}/storage/v1/object/public/{bucket}/{clean_path}"
        return f"/static/storage/{bucket}/{clean_path}"

    async def delete_file(self, bucket: str, path: str) -> bool:
        clean_path = path.lstrip("/")
        if self.is_cloud_enabled:
            url = f"{self.supabase_url}/storage/v1/object/{bucket}/{clean_path}"
            headers = {"Authorization": f"Bearer {self.service_key}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(url, headers=headers)
                return resp.status_code in (200, 204)
        else:
            local_file = self.storage_dir / bucket / clean_path
            if local_file.exists():
                local_file.unlink()
                return True
            return False


supabase_storage = SupabaseStorageHelper()

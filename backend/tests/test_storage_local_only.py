"""Local-only storage: ảnh không lên cloud.

RED: các test này phải FAIL khi còn code cloud (storage3 / signed URL /
is_cloud_enabled), PASS sau khi dọn xong.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _src(rel: str) -> str:
    return (Path(__file__).resolve().parents[1] / rel).read_text(encoding="utf-8")


def test_core_supabase_khong_cloud():
    src = _src("src/detect_ai/shared/kernel/supabase.py")
    assert "storage3" not in src
    assert "create_client" not in src
    assert "is_cloud_enabled" not in src
    assert "create_signed_url" not in src
    assert "signedURL" not in src


def test_routes_files_khong_signed_url():
    src = _src("src/detect_ai/modules/reporting/presentation/files_routes.py")
    assert "create_signed_url" not in src
    assert "signedURL" not in src
    assert "is_cloud_enabled" not in src


def test_routes_kiosk_khong_download_cloud():
    src = _src("src/detect_ai/modules/attendance/presentation/kiosk_routes.py")
    assert ".download(" not in src
    assert "is_cloud_enabled" not in src


def test_pyproject_khong_storage3():
    src = _src("pyproject.toml")
    assert "storage3" not in src


@pytest.mark.asyncio
async def test_upload_luu_dia_local(tmp_path):
    from detect_ai.shared.kernel.supabase import SupabaseStorageHelper

    storage = SupabaseStorageHelper(storage_dir=tmp_path)
    url = await storage.upload_file(
        bucket=SupabaseStorageHelper.BUCKET_LEAVE_PROOFS,
        path="local_only.png",
        content=b"fake-image-bytes",
        content_type="image/png",
    )
    assert url == "/api/v1/files/leave-proof/local_only.png"
    assert (tmp_path / "leave-proofs" / "local_only.png").read_bytes() == b"fake-image-bytes"
    assert await storage.delete_file(
        SupabaseStorageHelper.BUCKET_LEAVE_PROOFS, "local_only.png"
    ) is True

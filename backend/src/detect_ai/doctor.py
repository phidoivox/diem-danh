"""Chẩn đoán cấu hình CSDL / Storage local — chạy trước khi tin là đã cấu hình đúng.

    uv run python -m detect_ai.doctor
    # hoặc
    uv run detect-ai-doctor

Không kết nối ra ngoài. Thoát mã 0 nếu mọi thứ OK, 1 nếu có FAIL.
"""
from __future__ import annotations

import sys
from typing import List, Tuple

from sqlalchemy import text

from .shared.kernel.config import BASE_DIR, DATABASE_URL, S
from .shared.kernel.database import (
    Session,
    engine,
    is_sqlite,
    is_supabase,
    uses_transaction_pooler,
)
from .shared.kernel.supabase import STORAGE_DIR

OK, WARN, FAIL, INFO = "[ OK ]", "[WARN]", "[FAIL]", "[INFO]"

_findings: List[Tuple[str, str]] = []


def _say(level: str, message: str) -> None:
    _findings.append((level, message))
    print(f"{level} {message}")


def _describe_secret(value: str) -> str:
    """Mô tả secret mà KHÔNG lộ ký tự nào — output của doctor được thiết kế để dán
    vào issue/chat khi cần hỗ trợ, nên tuyệt đối không in một phần secret."""
    if not value:
        return "(trống)"
    return f"đã đặt ({len(value)} ký tự)"


def _section(title: str) -> None:
    print()
    print("-" * 68)
    print(f" {title}")
    print("-" * 68)


def check_config() -> None:
    _section("1. Cấu hình")

    env_file = BASE_DIR / ".env"
    if env_file.exists():
        _say(OK, f"Tìm thấy {env_file}")
    else:
        _say(WARN, f"Không có {env_file} — đang dùng giá trị mặc định trong core/config.py")

    mode = "SQLite (offline)" if is_sqlite else "PostgreSQL/Supabase"
    _say(INFO, f"Chế độ CSDL      : {mode}")
    _say(INFO, f"DATABASE_URL     : {engine.url.render_as_string(hide_password=True)}")

    if not is_sqlite:
        _say(INFO, f"Supabase         : {'có' if is_supabase(DATABASE_URL) else 'không (Postgres thường)'}")
        if uses_transaction_pooler(DATABASE_URL):
            _say(OK, "Transaction pooler (cổng 6543) — đã tự tắt prepared statement cache")
        else:
            _say(INFO, "Không dùng transaction pooler — giữ nguyên prepared statement cache")

    _say(INFO, f"Tự create_all    : {S.auto_create_tables}")
    if not is_sqlite and S.auto_create_tables:
        _say(WARN, "Đang bật AUTO_CREATE_TABLES trên Postgres. Nên đặt "
                   "DETECT_AI_AUTO_CREATE_TABLES=false để schema chỉ do backend/sql/ sở hữu.")

    if len(S.jwt_secret or "") < 32:
        _say(FAIL, "DETECT_AI_JWT_SECRET chưa đặt (>= 32 ký tự) — app sẽ từ chối khởi động")
    else:
        _say(OK, f"JWT secret {_describe_secret(S.jwt_secret)}")


async def check_database() -> None:
    _section("2. Kết nối CSDL")

    probe = "SELECT sqlite_version()" if is_sqlite else "SELECT version()"
    try:
        async with engine.connect() as conn:
            version = (await conn.execute(text(probe))).scalar_one()
            _say(OK, f"Kết nối thành công: {str(version)[:70]}")
    except Exception as exc:
        _say(FAIL, f"Không kết nối được CSDL: {type(exc).__name__}: {str(exc)[:160]}")
        if not is_sqlite:
            _say(INFO, "Gợi ý: kiểm tra DETECT_AI_SUPABASE_DB_URL (mật khẩu phải URL-encode), "
                       "và nhớ dùng cổng 5432 (session pooler) hoặc 6543 (transaction pooler).")
        return

    from . import models  # noqa: F401
    from .shared.kernel.database import Base

    expected = set(Base.metadata.tables)

    if is_sqlite:
        rows = await _scalars("SELECT name FROM sqlite_master WHERE type='table'")
    else:
        rows = await _scalars("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    present = set(rows)

    missing = sorted(expected - present)
    if missing:
        _say(FAIL, f"Thiếu {len(missing)} bảng: {', '.join(missing)}")
        _say(INFO, "Chạy backend/sql/01_schema.sql (bản mới) rồi 02_seed.sql trên SQL Editor.")
    else:
        _say(OK, f"Đủ {len(expected)} bảng cần thiết")

    # --- cột status: phát hiện CSDL còn schema cũ ---
    # Tên bảng hardcode ở call-site (không từ input user) — không nội suy
    # string lạ vào SQL. Muốn check thêm bảng: thêm literal vào tuple.
    for table in ("attendance", "leave_requests"):
        assert table in ("attendance", "leave_requests")
        if is_sqlite:
            cols = await _sqlite_columns(table)
            if "status" in cols:
                _say(OK, f"{table}.status tồn tại")
            else:
                _say(FAIL, f"{table} thiếu cột 'status' -> bảng đang ở schema legacy. "
                           f"Xoá backend/data/detect_ai.db* rồi khởi động lại để tạo đúng.")
        else:
            dtype = await _scalars(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:table AND column_name='status'",
                {"table": table},
            )
            if not dtype:
                _say(FAIL, f"{table}.status: không tìm thấy cột -> schema lệch, chạy lại 01_schema.sql")
            elif dtype[0] == "USER-DEFINED":
                _say(FAIL, f"{table}.status vẫn là ENUM native -> asyncpg sẽ lỗi khi ghi. "
                           f"Chạy backend/sql/03_migrate_existing_db.sql")
            else:
                _say(OK, f"{table}.status = {dtype[0]} (đúng dạng VARCHAR)")

    if is_sqlite:
        return

    # --- kiểm tra riêng cho Postgres/Supabase ---
    extensions = set(await _scalars("SELECT extname FROM pg_extension"))
    if "pgcrypto" in extensions or "uuid-ossp" in extensions:
        _say(OK, f"Extension: {', '.join(sorted(extensions & {'pgcrypto', 'uuid-ossp'}))}")
    else:
        _say(INFO, "Chưa bật pgcrypto/uuid-ossp (chỉ cần nếu bạn dùng UUID do DB sinh)")

    if "vector" in extensions:
        _say(INFO, "Extension 'vector' (pgvector) đã bật (không còn bắt buộc sau khi bỏ FaceID)")
    else:
        _say(INFO, "Chưa bật pgvector (không cần thiết sau khi đã bỏ FaceID)")


async def _sqlite_columns(table: str) -> set:
    assert table in ("attendance", "leave_requests")
    async with Session() as session:
        result = await session.execute(text(f"PRAGMA table_info({table})"))
        return {str(row[1]) for row in result.all()}


async def _scalars(sql: str, params: dict | None = None) -> List[str]:
    async with Session() as session:
        result = await session.execute(text(sql), params or {})
        return [str(r[0]) for r in result.all()]


def check_storage() -> None:
    _section("3. Storage (local)")

    _say(OK, f"Ảnh lưu local, không upload cloud: {STORAGE_DIR}")
    for sub in ("leave-proofs", "avatars", "snapshots"):
        p = STORAGE_DIR / sub
        if p.is_dir():
            _say(OK, f"Thư mục '{sub}' OK")
        else:
            _say(INFO, f"Thư mục '{sub}' chưa có (tự tạo khi upload ảnh đầu tiên)")
    _say(INFO, "Avatars qua /api/v1/files/avatar (auth)")


def main() -> int:
    print("=" * 68)
    print(" detect-ai — chẩn đoán cấu hình")
    print("=" * 68)

    check_config()
    import asyncio

    asyncio.run(check_database())
    check_storage()

    fails = [m for lvl, m in _findings if lvl == FAIL]
    warns = [m for lvl, m in _findings if lvl == WARN]

    _section("Kết luận")
    if fails:
        print(f"{FAIL} {len(fails)} vấn đề nghiêm trọng, {len(warns)} cảnh báo:")
        for m in fails:
            print(f"       - {m}")
        return 1
    if warns:
        print(f"{WARN} Không có lỗi chặn, nhưng có {len(warns)} cảnh báo:")
        for m in warns:
            print(f"       - {m}")
        return 0
    print(f"{OK} Cấu hình đầy đủ và hợp lệ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

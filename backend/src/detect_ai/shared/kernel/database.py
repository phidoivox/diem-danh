from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from .config import DATABASE_URL, S

is_sqlite = DATABASE_URL.startswith("sqlite")
is_postgres = DATABASE_URL.startswith("postgresql")


def is_supabase(url: str) -> bool:
    """True nếu URL trỏ tới Supabase (direct host hoặc Supavisor pooler)."""
    return any(h in url for h in ("supabase.co", "supabase.com", "supabase.net", "pooler.supabase"))


def uses_transaction_pooler(url: str) -> bool:
    """Supavisor transaction mode chạy ở cổng 6543.

    Chế độ này KHÔNG giữ prepared statement giữa các request, trong khi asyncpg mặc
    định cache prepared statement -> lỗi rất khó đoán:
        prepared statement "__asyncpg_stmt_1__" already exists
    Session mode (cổng 5432) thì giữ được, không cần tắt cache.
    """
    return ":6543" in url


def postgres_connect_args(url: str) -> dict:
    """Tham số kết nối asyncpg phù hợp với Supabase."""
    args: dict = {"command_timeout": 60}
    # CHỈ ép SSL với Supabase — Postgres tự dựng/localhost thường không bật SSL,
    # ép vào sẽ lỗi "server does not support SSL".
    # Nếu URL đã có ?sslmode=... thì để asyncpg tự xử lý, tránh truyền trùng.
    # asyncpg nhận thẳng chuỗi sslmode qua tham số `ssl`.
    if is_supabase(url) and "sslmode=" not in url:
        args["ssl"] = "require"
    if uses_transaction_pooler(url):
        args["statement_cache_size"] = 0
        args["max_cached_statement_lifetime"] = 0
    return args


def default_pool(url: str) -> tuple[int, int]:
    """(pool_size, max_overflow) mặc định.

    Supabase giới hạn số kết nối khá chặt (gói Free ~60 ở direct, ~200 ở pooler),
    nên để pool nhỏ hơn Postgres tự dựng.
    """
    if is_supabase(url):
        return 5, 5
    return 10, 20


if is_sqlite:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"timeout": 30},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

else:
    _pool_size, _max_overflow = default_pool(DATABASE_URL)
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=S.db_pool_size or _pool_size,
        max_overflow=S.db_max_overflow or _max_overflow,
        pool_pre_ping=True,
        # Supabase/Supavisor đóng kết nối idle; recycle sớm hơn để tránh dùng kết nối đã chết.
        pool_recycle=1800,
        connect_args=postgres_connect_args(DATABASE_URL),
    )

Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Tạo các bảng còn thiếu từ metadata (chỉ khi auto_create_tables bật).

    LƯU Ý: create_all KHÔNG ALTER bảng đã tồn tại và KHÔNG tạo index còn thiếu trên
    bảng cũ. Chạy trên Supabase nên đặt DETECT_AI_AUTO_CREATE_TABLES=false để schema
    chỉ do backend/sql/ sở hữu — nếu không sẽ quay lại đúng cái drift hai nguồn sự thật.
    """
    if not S.auto_create_tables:
        return
    from .. import models  # noqa: F401
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)

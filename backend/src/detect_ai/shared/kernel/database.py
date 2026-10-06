from __future__ import annotations
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import DATABASE_URL

is_sqlite = DATABASE_URL.startswith("sqlite")

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
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )

Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    # Qua public (đăng ký Base.metadata qua re-export models, không import sâu infra).
    from detect_ai.modules.academic import public as _academic_public  # noqa: F401
    from detect_ai.modules.attendance import public as _attendance_public  # noqa: F401
    from detect_ai.modules.evaluation import public as _evaluation_public  # noqa: F401
    from detect_ai.modules.identity import public as _identity_public  # noqa: F401
    from detect_ai.modules.leave import public as _leave_public  # noqa: F401
    from detect_ai.modules.recognition import public as _recognition_public  # noqa: F401
    from detect_ai.shared.kernel import system_setting  # noqa: F401
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
        if is_sqlite:
            # Migration check for legacy sqlite table students
            cols = await c.run_sync(lambda sc: [r[1] for r in sc.exec_driver_sql("PRAGMA table_info(students)").fetchall()])
            if cols and "photo" not in cols:
                await c.exec_driver_sql("ALTER TABLE students ADD COLUMN photo VARCHAR(64) DEFAULT ''")

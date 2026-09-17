from __future__ import annotations
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from .config import DATABASE_URL

# timeout=30 + WAL mode: saver worker + request doc ghi song song khong bi database is locked.
engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"timeout": 30})
Session = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


class Base(DeclarativeBase):
    pass

async def init_db() -> None:
    from .. import models  # noqa: F401
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
        # migrate nhe: DB cu thieu cot photo (create_all khong ALTER)
        cols = await c.run_sync(lambda sc: [r[1] for r in sc.exec_driver_sql("PRAGMA table_info(students)").fetchall()])
        if "photo" not in cols:
            await c.exec_driver_sql("ALTER TABLE students ADD COLUMN photo VARCHAR(64) DEFAULT ''")

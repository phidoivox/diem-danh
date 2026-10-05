"""Shared factory fixtures for backend tests (Task 1).

KHÔNG sửa hành vi nghiệp vụ — chỉ cung cấp fixture dùng chung:
- engine_fixture: sqlite+aiosqlite memory, PRAGMA foreign_keys=ON, create_all/drop_all.
- session_maker_fixture: async_sessionmaker(expire_on_commit=False).
- make_client: factory tạo AsyncClient với get_db override + dọn /api/test routes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from detect_ai.core.database import Base
from detect_ai.core.deps import get_db
from detect_ai.main import app

import detect_ai.models  # noqa: F401  (đăng ký metadata trước create_all)


@pytest_asyncio.fixture
async def engine_fixture() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session_maker_fixture(
    engine_fixture: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    return async_sessionmaker(engine_fixture, expire_on_commit=False, class_=AsyncSession)


def _remove_test_routes() -> None:
    app.routes[:] = [
        r for r in app.routes if not getattr(r, "path", "").startswith("/api/test")
    ]
    try:
        if app.router.routes is not app.routes:
            app.router.routes[:] = [
                r
                for r in app.router.routes
                if not getattr(r, "path", "").startswith("/api/test")
            ]
    except Exception:
        pass


def _clear_recognition_caches() -> None:
    # Gallery/pipeline cache giữ theo class_id/schedule_id (process-global):
    # test trước nạp gallery của class khác vào cùng slot id sẽ rò sang
    # test sau (VD gallery_size 30 thay vì 1). Xóa để mỗi client HTTP thấy
    # đúng dữ liệu fixture của chính nó.
    try:
        from detect_ai.recognition import gallery as _gal_mod
        from detect_ai.recognition import pipeline as _pipe_mod

        _gal_mod._cache.clear()
        _pipe_mod._sessions.clear()
    except Exception:
        pass


@pytest_asyncio.fixture
async def make_client(session_maker_fixture):
    """Factory tạo AsyncClient cho test.

    Dùng: async with make_client() as client:
    Sau yield mỗi client: đóng client, app.dependency_overrides.clear(),
    gỡ mọi route có path startswith /api/test.
    """

    clients: list[AsyncClient] = []

    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncClient]:
        async def override_get_db():
            async with session_maker_fixture() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        transport = ASGITransport(app=app)
        client = AsyncClient(transport=transport, base_url="http://testserver")
        clients.append(client)
        try:
            yield client
        finally:
            await client.aclose()
            app.dependency_overrides.clear()
            _remove_test_routes()
            _clear_recognition_caches()

    yield _factory

    for c in clients:
        try:
            if not c.is_closed:
                await c.aclose()
        except Exception:
            pass
    app.dependency_overrides.clear()
    _remove_test_routes()
    _clear_recognition_caches()

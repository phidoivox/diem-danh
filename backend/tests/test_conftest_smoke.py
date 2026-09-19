import pytest
from sqlalchemy import select

from detect_ai.models.user import Role


@pytest.mark.asyncio
async def test_engine_empty(session_maker_fixture):
    async with session_maker_fixture() as session:
        result = await session.execute(select(Role))
        assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_make_client_health(make_client):
    async with make_client() as client:
        res = await client.get("/api/health")
        assert res.status_code == 200

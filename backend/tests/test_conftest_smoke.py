import pytest
from sqlalchemy import select

from detect_ai.models.user import Role


@pytest.mark.asyncio
async def test_engine_empty(session_maker_fixture):
    async with session_maker_fixture() as session:
        result = await session.execute(select(Role))
        assert result.scalars().all() == []

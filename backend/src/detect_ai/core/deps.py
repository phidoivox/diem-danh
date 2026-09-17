from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from .database import Session

async def get_db() -> AsyncSession:
    async with Session() as s:
        yield s

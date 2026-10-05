from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession


async def get_schedule(session: AsyncSession, schedule_id: int):
    from .infrastructure.models import Schedule
    return await session.get(Schedule, schedule_id)


async def get_class(session: AsyncSession, class_id: int):
    from .infrastructure.models import Class
    return await session.get(Class, class_id)

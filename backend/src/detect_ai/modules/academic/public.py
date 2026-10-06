from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .infrastructure.models import Class, ClassStudent, Course, Schedule  # noqa: F401


async def get_schedule(session: AsyncSession, schedule_id: int):
    from .infrastructure.models import Schedule
    return await session.get(Schedule, schedule_id)


async def get_class(session: AsyncSession, class_id: int):
    from .infrastructure.models import Class
    return await session.get(Class, class_id)


__all__ = [
    "Class",
    "ClassStudent",
    "Course",
    "Schedule",
    "get_class",
    "get_schedule",
    "academic_router",
]


def __getattr__(name: str):
    # Lazy: presentation.routes import application.* (import ngược public khác),
    # eager ở đây gây circular import. main.py vẫn `from .public import academic_router`.
    if name == "academic_router":
        from .presentation.routes import router as academic_router

        return academic_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

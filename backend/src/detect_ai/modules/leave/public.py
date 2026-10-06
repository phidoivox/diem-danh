from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .domain.request import LeaveStatus
from .infrastructure.models import LeaveRequest  # noqa: F401


async def is_excused(
    session: AsyncSession,
    schedule_id: int,
    student_id: int,
) -> bool:
    """Return True if an APPROVED leave exists for (schedule_id, student_id)."""
    stmt = (
        select(LeaveRequest.id)
        .where(
            LeaveRequest.schedule_id == schedule_id,
            LeaveRequest.student_id == student_id,
            LeaveRequest.status == LeaveStatus.APPROVED,
        )
        .limit(1)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none() is not None


__all__ = ["LeaveRequest", "LeaveStatus", "is_excused", "leave_router"]


def __getattr__(name: str):
    # Lazy: xem academic/public.py (tránh circular import qua application.review).
    if name == "leave_router":
        from .presentation.routes import router as leave_router

        return leave_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

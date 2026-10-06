from __future__ import annotations

"""Repo cho attendance commit: query Attendance theo batch (giữ 1 SELECT/frame)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def list_attendances_by_students(
    session: AsyncSession, schedule_id: int, student_ids: list[int]
) -> list:
    """Repo cho commit: Attendance của (schedule, students), giữ nguyên where."""
    from detect_ai.modules.attendance.public import Attendance

    stmt = select(Attendance).where(
        Attendance.schedule_id == schedule_id,
        Attendance.student_id.in_(student_ids),
    )
    return (await session.execute(stmt)).scalars().all()


__all__ = ["list_attendances_by_students"]

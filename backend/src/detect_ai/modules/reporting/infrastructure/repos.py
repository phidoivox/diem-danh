"""Repo cho reporting/application/build (Task 4): gom select(...) khỏi application.

Application chỉ gọi repo + domain policy + settings; giữ nguyên logic lọc,
order, batch SELECT (không N+1), ngưỡng warning/ban.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from detect_ai.modules.academic.public import Class, ClassStudent, Schedule
from detect_ai.modules.attendance.public import Attendance
from detect_ai.modules.identity.public import User


async def get_class_with_details(session: AsyncSession, class_id: int):
    stmt = (
        select(Class)
        .options(selectinload(Class.teacher), selectinload(Class.course))
        .where(Class.id == class_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_classes_ordered(session: AsyncSession) -> list:
    stmt = select(Class).options(selectinload(Class.course)).order_by(Class.class_code)
    return (await session.execute(stmt)).scalars().all()


async def list_enrolled_students(session: AsyncSession, class_id: int) -> list:
    stmt = (
        select(User)
        .join(ClassStudent, ClassStudent.student_id == User.id)
        .options(selectinload(User.student_profile))
        .where(
            ClassStudent.class_id == class_id,
            User.is_active == True,
            User.deleted_at.is_(None),
        )
        .order_by(User.user_code)
    )
    return (await session.execute(stmt)).scalars().all()


async def list_schedules_by_class(
    session: AsyncSession, class_id: int, reference_date
) -> list:
    stmt = (
        select(Schedule)
        .where(Schedule.class_id == class_id, Schedule.study_date <= reference_date)
        .order_by(Schedule.study_date, Schedule.start_time)
    )
    return (await session.execute(stmt)).scalars().all()


async def list_attendances_by_schedules(
    session: AsyncSession, schedule_ids: list
) -> list:
    stmt = select(Attendance).where(Attendance.schedule_id.in_(schedule_ids))
    return (await session.execute(stmt)).scalars().all()


async def get_history_bundle(session: AsyncSession, class_id: int, student_id: int):
    """Bundle cho build_student_history: (class, enrolled, student, schedules, atts, ledger)."""
    class_obj = (
        await session.execute(
            select(Class)
            .options(selectinload(Class.teacher), selectinload(Class.course))
            .where(Class.id == class_id)
        )
    ).scalar_one_or_none()
    enrolled = (
        await session.execute(
            select(ClassStudent).where(
                ClassStudent.class_id == class_id,
                ClassStudent.student_id == student_id,
            )
        )
    ).scalar_one_or_none()
    student = await session.get(User, student_id)
    schedules = (
        await session.execute(
            select(Schedule)
            .where(Schedule.class_id == class_id)
            .order_by(Schedule.study_date.asc(), Schedule.start_time.asc())
        )
    ).scalars().all()
    sched_ids = [s.id for s in schedules]
    atts = []
    if sched_ids:
        atts = (
            await session.execute(
                select(Attendance).where(
                    Attendance.student_id == student_id,
                    Attendance.schedule_id.in_(sched_ids),
                )
            )
        ).scalars().all()
    from detect_ai.modules.evaluation.public import PointLedger
    ledger = []
    if sched_ids:
        ledger = (
            await session.execute(
                select(PointLedger).where(
                    PointLedger.student_id == student_id,
                    PointLedger.schedule_id.in_(sched_ids),
                )
            )
        ).scalars().all()
    return class_obj, enrolled, student, list(schedules), list(atts), list(ledger)

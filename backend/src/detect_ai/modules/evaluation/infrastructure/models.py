from __future__ import annotations
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship
from detect_ai.shared.kernel.database import Base

if TYPE_CHECKING:
    from detect_ai.modules.identity.public import User
    from detect_ai.modules.academic.public import Schedule


class PointLedger(Base):
    __tablename__ = "point_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    schedule_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True
    )
    point_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_point_ledger_student", "student_id"),
        Index("idx_point_ledger_schedule", "schedule_id"),
    )

    student: Mapped[User] = relationship(
        "User",
        foreign_keys=[student_id],
        back_populates="point_ledger_entries",
    )
    schedule: Mapped[Optional[Schedule]] = relationship(
        "Schedule",
        foreign_keys=[schedule_id],
        back_populates="point_ledger_entries",
    )


async def list_schedules_by_date(session: AsyncSession, target_date: date) -> list:
    """Repo cho nightly: lịch học đúng ngày, giữ nguyên order_by(id)."""
    from detect_ai.modules.academic.public import Schedule

    stmt = select(Schedule).where(Schedule.study_date == target_date).order_by(Schedule.id)
    return (await session.execute(stmt)).scalars().all()


async def list_enrolled_student_ids(session: AsyncSession, class_id: int) -> list:
    """Repo cho nightly: student_id enrolled trong lớp."""
    from detect_ai.modules.academic.public import ClassStudent

    stmt = select(ClassStudent.student_id).where(ClassStudent.class_id == class_id)
    return (await session.execute(stmt)).scalars().all()


async def list_attendances_by_schedule(session: AsyncSession, schedule_id: int) -> list:
    """Repo cho nightly: bản ghi điểm danh của 1 buổi."""
    from detect_ai.modules.attendance.public import Attendance

    stmt = select(Attendance).where(Attendance.schedule_id == schedule_id)
    return (await session.execute(stmt)).scalars().all()


async def list_profiles_by_user_ids(session: AsyncSession, user_ids: list) -> list:
    """Repo cho nightly: batch 1 query profiles (giữ batch, không N+1)."""
    from detect_ai.modules.identity.public import StudentProfile

    stmt = select(StudentProfile).where(StudentProfile.user_id.in_(user_ids))
    return (await session.execute(stmt)).scalars().all()


async def list_approved_leave_student_ids(
    session: AsyncSession, schedule_id: int, student_ids: list
) -> set:
    """Repo cho nightly: batch 1 query đơn APPROVED (giữ batch, không N+1)."""
    from detect_ai.modules.leave.public import LeaveRequest, LeaveStatus

    stmt = select(LeaveRequest.student_id).where(
        LeaveRequest.schedule_id == schedule_id,
        LeaveRequest.student_id.in_(student_ids),
        LeaveRequest.status == LeaveStatus.APPROVED,
    )
    return set((await session.execute(stmt)).scalars().all())

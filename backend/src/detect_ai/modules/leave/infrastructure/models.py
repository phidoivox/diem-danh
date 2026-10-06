from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from detect_ai.shared.kernel.database import Base
from ..domain.request import LeaveStatus

if TYPE_CHECKING:
    from detect_ai.modules.identity.public import User
    from detect_ai.modules.academic.public import Schedule


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    proof_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[LeaveStatus] = mapped_column(
        SQLEnum(
            LeaveStatus,
            name="leave_status",
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=LeaveStatus.PENDING,
        nullable=False,
    )
    teacher_feedback: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_leave_requests_student_id", "student_id"),
        Index("idx_leave_requests_schedule_id", "schedule_id"),
    )

    schedule: Mapped[Schedule] = relationship("Schedule", back_populates="leave_requests")
    student: Mapped[User] = relationship(
        "User",
        foreign_keys=[student_id],
        back_populates="leave_requests",
    )
    reviewer: Mapped[Optional[User]] = relationship(
        "User",
        foreign_keys=[reviewed_by],
    )


__all__ = [
    "LeaveRequest",
    "LeaveStatus",
    "find_attendance",
    "find_refund_entry",
    "find_student_profile",
    "list_deduct_ledger_entries",
]


async def find_attendance(
    session: AsyncSession, schedule_id: int, student_id: int
):
    """Repo cho review: bản ghi điểm danh của (schedule, student), giữ nguyên logic."""
    from detect_ai.modules.attendance.public import Attendance

    stmt = select(Attendance).where(
        Attendance.schedule_id == schedule_id,
        Attendance.student_id == student_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_deduct_ledger_entries(
    session: AsyncSession, student_id: int, schedule_id: int
) -> list:
    """Repo cho review: các dòng ledger trừ điểm (giữ nguyên point_delta < 0)."""
    from detect_ai.modules.evaluation.public import PointLedger

    stmt = select(PointLedger).where(
        PointLedger.student_id == student_id,
        PointLedger.schedule_id == schedule_id,
        PointLedger.point_delta < 0,
    )
    return (await session.execute(stmt)).scalars().all()


async def find_refund_entry(
    session: AsyncSession, student_id: int, schedule_id: int
):
    """Repo cho review: dòng LEAVE_REFUND đã có (chống hoàn điểm 2 lần)."""
    from detect_ai.modules.evaluation.public import PointLedger

    stmt = select(PointLedger).where(
        PointLedger.student_id == student_id,
        PointLedger.schedule_id == schedule_id,
        PointLedger.reason_code == "LEAVE_REFUND",
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def find_student_profile(session: AsyncSession, student_id: int):
    """Repo cho review: StudentProfile theo user_id."""
    from detect_ai.modules.identity.public import StudentProfile

    stmt = select(StudentProfile).where(StudentProfile.user_id == student_id)
    return (await session.execute(stmt)).scalar_one_or_none()

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from detect_ai.shared.kernel.database import Base
from ..domain.request import LeaveStatus

if TYPE_CHECKING:
    from detect_ai.models.user import User
    from detect_ai.models.academic import Schedule


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


__all__ = ["LeaveRequest", "LeaveStatus"]

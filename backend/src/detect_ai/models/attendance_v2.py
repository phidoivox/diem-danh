from __future__ import annotations
import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base

if TYPE_CHECKING:
    from .user import User
    from .academic import Schedule


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    LATE = "LATE"
    HALF_ABSENT = "HALF_ABSENT"
    ABSENT = "ABSENT"
    EXCUSED = "EXCUSED"


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    check_in_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    check_out_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    has_uniform: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    uniform_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    uniform_status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    status: Mapped[AttendanceStatus] = mapped_column(
        SQLEnum(
            AttendanceStatus,
            name="attendance_status",
            native_enum=False,
            # create_constraint: native_enum=False một mình chỉ cho ra VARCHAR trần,
            # mất hẳn kiểm tra giá trị mà ENUM native của Postgres vẫn có. Bật lên để
            # cả SQLite lẫn Postgres đều có CHECK (status IN (...)).
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=AttendanceStatus.ABSENT,
        nullable=False,
    )
    is_manual_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_evaluated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Snapshot khuôn mặt lúc check-in/out (URL local /static/storage/snapshots/...).
    # Chỉ lưu tối đa 2 ảnh/người/tiết, chụp đúng lúc transition, không lưu mỗi frame.
    check_in_snapshot_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    check_out_snapshot_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("schedule_id", "student_id", name="uq_attendance_schedule_student"),
        Index("idx_attendance_schedule_student", "schedule_id", "student_id"),
        Index("idx_attendance_evaluated", "is_evaluated", "schedule_id"),
    )

    schedule: Mapped[Schedule] = relationship("Schedule", back_populates="attendances")
    student: Mapped[User] = relationship(
        "User",
        foreign_keys=[student_id],
        back_populates="attendances",
    )
    updater: Mapped[Optional[User]] = relationship(
        "User",
        foreign_keys=[updated_by],
    )

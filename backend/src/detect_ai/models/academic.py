from __future__ import annotations
from datetime import date, time
from typing import TYPE_CHECKING, List
from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base

if TYPE_CHECKING:
    from .user import User
    from .attendance_v2 import Attendance
    from .leave_request import LeaveRequest
    from .point_ledger import PointLedger


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    course_name: Mapped[str] = mapped_column(String(100), nullable=False)
    teacher_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    total_sessions: Mapped[int] = mapped_column(Integer, default=15, nullable=False)

    teacher: Mapped[User] = relationship(
        "User",
        back_populates="teaching_classes",
        foreign_keys=[teacher_id],
        lazy="selectin",
    )
    students: Mapped[List[User]] = relationship(
        "User",
        secondary="class_students",
        back_populates="enrolled_classes",
    )
    schedules: Mapped[List[Schedule]] = relationship(
        "Schedule",
        back_populates="clazz",
        cascade="all, delete-orphan",
    )


class ClassStudent(Base):
    __tablename__ = "class_students"

    class_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_name: Mapped[str] = mapped_column(String(50), nullable=False)
    study_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    session_order: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("start_time < end_time", name="check_schedule_time_valid"),
        Index("idx_schedules_room_date", "room_name", "study_date"),
        Index("idx_schedules_room_conflict", "room_name", "study_date", "start_time", "end_time"),
    )

    clazz: Mapped[Class] = relationship("Class", back_populates="schedules", lazy="selectin")
    attendances: Mapped[List[Attendance]] = relationship(
        "Attendance",
        back_populates="schedule",
        cascade="all, delete-orphan",
    )
    leave_requests: Mapped[List[LeaveRequest]] = relationship(
        "LeaveRequest",
        back_populates="schedule",
        cascade="all, delete-orphan",
    )
    point_ledger_entries: Mapped[List[PointLedger]] = relationship(
        "PointLedger",
        back_populates="schedule",
    )

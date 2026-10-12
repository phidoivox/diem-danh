from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from detect_ai.shared.kernel.database import Base

if TYPE_CHECKING:
    from detect_ai.modules.identity.public import User
    from detect_ai.modules.attendance.public import Attendance
    from detect_ai.modules.leave.public import LeaveRequest
    from detect_ai.modules.evaluation.public import PointLedger


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    default_sessions: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    classes: Mapped[List[Class]] = relationship(
        "Class",
        back_populates="course",
    )


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    course_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # ponytail: schema SQL (01_schema.sql) giữ NOT NULL + backfill; model nullable để
    # fixtures/tests cũ (17 chỗ tạo Class không có course) chạy được. Production reads
    # không ảnh hưởng. Khi fixtures được cập nhật hết, siết lại nullable=False.
    course_name: Mapped[str] = mapped_column(String(100), nullable=False)
    teacher_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    total_sessions: Mapped[int] = mapped_column(Integer, default=15, nullable=False)

    course: Mapped[Course] = relationship(
        "Course",
        back_populates="classes",
        foreign_keys=[course_id],
        lazy="selectin",
    )

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


class AdministrativeClass(Base):
    __tablename__ = "administrative_classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    academic_year: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    faculty: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    homeroom_teacher_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    homeroom_teacher: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[homeroom_teacher_id],
        lazy="selectin",
    )


__all__ = ["AdministrativeClass", "Class", "ClassStudent", "Course", "Schedule"]


from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base

if TYPE_CHECKING:
    from .academic import Class
    from .attendance_v2 import Attendance
    from .leave_request import LeaveRequest
    from .point_ledger import PointLedger


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    users: Mapped[List[User]] = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    role: Mapped[Role] = relationship("Role", back_populates="users", lazy="selectin")
    student_profile: Mapped[Optional[StudentProfile]] = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    teacher_profile: Mapped[Optional[TeacherProfile]] = relationship(
        "TeacherProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    teaching_classes: Mapped[List[Class]] = relationship(
        "Class",
        back_populates="teacher",
        foreign_keys="Class.teacher_id",
    )
    enrolled_classes: Mapped[List[Class]] = relationship(
        "Class",
        secondary="class_students",
        back_populates="students",
    )
    attendances: Mapped[List[Attendance]] = relationship(
        "Attendance",
        back_populates="student",
        foreign_keys="Attendance.student_id",
    )
    leave_requests: Mapped[List[LeaveRequest]] = relationship(
        "LeaveRequest",
        back_populates="student",
        foreign_keys="LeaveRequest.student_id",
    )
    point_ledger_entries: Mapped[List[PointLedger]] = relationship(
        "PointLedger",
        back_populates="student",
        foreign_keys="PointLedger.student_id",
    )


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    face_embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_point: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    class_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    major: Mapped[str] = mapped_column(String(100), default="", nullable=False)

    user: Mapped[User] = relationship("User", back_populates="student_profile", lazy="selectin")


class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    department: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    academic_title: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    office_room: Mapped[str] = mapped_column(String(50), default="", nullable=False)

    user: Mapped[User] = relationship("User", back_populates="teacher_profile", lazy="selectin")

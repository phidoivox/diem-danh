from __future__ import annotations
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base

class AttendanceRecord(Base):
    __tablename__ = "legacy_attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    student_code: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    uniform_status: Mapped[str] = mapped_column(String(16), default="unknown")  # ok|violation|unknown
    violations: Mapped[str] = mapped_column(String(256), default="")
    snapshot: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from detect_ai.shared.kernel.database import Base


class FaceEmbedding(Base):
    """Vector đặc trưng khuôn mặt (ArcFace 512D) của 1 user.

    SQLite: embedding lưu JSON text (list 512 float).
    Postgres: vẫn VARCHAR/TEXT JSON trừ khi admin tự tạo cột vector(512) —
    tầng service chỉ đọc/ghi JSON nên tương thích cả hai.
    """

    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    embedding: Mapped[str] = mapped_column(Text, nullable=False)
    quality: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="avatar", nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), default="buffalo_s", nullable=False)
    det_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_face_embeddings_user_active", "user_id", "is_active"),)


class FaceEvent(Base):
    """Audit từng quyết định của Kiosk (phục vụ khiếu nại + tuning ngưỡng)."""

    __tablename__ = "face_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    liveness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    margin: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    backend: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_face_events_schedule_time", "schedule_id", "created_at"),)


__all__ = ["FaceEmbedding", "FaceEvent"]

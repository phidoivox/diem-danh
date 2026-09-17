from __future__ import annotations
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base

class UniformRule(Base):
    __tablename__ = "uniform_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[str] = mapped_column(String(16), default="*")  # * = moi ngay
    require_shirt: Mapped[str] = mapped_column(String(32), default="valid_shirt")
    require_bottom: Mapped[str] = mapped_column(String(32), default="valid_pants|valid_skirt")
    require_id_card: Mapped[bool] = mapped_column(default=True)

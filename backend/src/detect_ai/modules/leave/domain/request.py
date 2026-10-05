from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import enum
from typing import Optional


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class LeaveRequestEntity:
    schedule_id: int
    student_id: int
    reason: str
    id: Optional[int] = None
    proof_image: Optional[str] = None
    status: LeaveStatus = LeaveStatus.PENDING
    teacher_feedback: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


LeaveRequest = LeaveRequestEntity

__all__ = ["LeaveRequest", "LeaveRequestEntity", "LeaveStatus"]

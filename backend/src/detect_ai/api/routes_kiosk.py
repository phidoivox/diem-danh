from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_db
from ..services.kiosk_service import record_kiosk_attendance
from .deps_auth import verify_kiosk_api_key

router = APIRouter(dependencies=[Depends(verify_kiosk_api_key)])


class KioskRecordRequest(BaseModel):
    room_name: str = Field(..., description="Tên phòng học đặt Kiosk (ví dụ: A1-301)")
    student_code: str = Field(..., description="Mã số sinh viên (ví dụ: SV2026001)")
    has_uniform: bool = Field(True, description="Trạng thái mặc đồng phục hợp lệ")
    timestamp: Optional[datetime] = Field(None, description="Thời điểm quét (mặc định là hiện tại)")


@router.post("/kiosk-record")
async def kiosk_record(
    req: KioskRecordRequest,
    s: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Ghi nhận lượt quét điểm danh từ thiết bị Kiosk AI."""
    return await record_kiosk_attendance(
        s=s,
        room_name=req.room_name,
        student_code=req.student_code,
        has_uniform=req.has_uniform,
        scan_time=req.timestamp,
    )

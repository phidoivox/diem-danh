from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.config import SNAPSHOT_DIR
from ..core.deps import get_db
from ..models.attendance import AttendanceRecord
from .files import safe_file

router = APIRouter(prefix="/api/attendance", tags=["attendance"])

@router.get("")
async def history(limit: int = 100, status: str = "", q: str = "",
                  s: AsyncSession = Depends(get_db)):
    # loc status + tim MSSV o server thay filter tay client
    stmt = select(AttendanceRecord)
    if status in ("ok", "violation"):
        stmt = stmt.where(AttendanceRecord.uniform_status == status)
    if q:
        stmt = stmt.where(AttendanceRecord.student_code.ilike(f"%{q}%"))
    rows = (await s.execute(stmt.order_by(desc(AttendanceRecord.id)).limit(min(limit, 500)))).scalars().all()
    return [{"id": r.id, "code": r.student_code, "uniform": r.uniform_status,
             "violations": r.violations, "snapshot": r.snapshot,
             "at": str(r.created_at)} for r in rows]

@router.get("/snapshot/{name}")
async def snapshot(name: str):
    return FileResponse(safe_file(SNAPSHOT_DIR, name))

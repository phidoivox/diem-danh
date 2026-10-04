from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.timeutil import today_vn
from ..models.academic import Class, Schedule


async def authorize_kiosk_schedule(db: AsyncSession, schedule_id: int, teacher_id: int) -> Schedule:
    stmt = (
        select(Schedule)
        .options(selectinload(Schedule.clazz).selectinload(Class.course))
        .where(Schedule.id == schedule_id)
    )
    sched = (await db.execute(stmt)).scalar_one_or_none()
    if not sched:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy buổi học")
    if not sched.clazz or sched.clazz.teacher_id != teacher_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không quản lý buổi học này")
    if sched.study_date != today_vn():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Hôm nay lớp không có tiết — điểm danh đang đóng")
    return sched


def adaptive_feedback(base_ms: int, max_width: int, infer_ms: float) -> tuple[int, int]:
    if infer_ms > 800:
        nxt, w = base_ms + 250, 416
    elif infer_ms > 500:
        nxt, w = base_ms + 100, int(max_width)
    else:
        nxt, w = base_ms, int(max_width)
    return max(120, min(nxt, 600)), w

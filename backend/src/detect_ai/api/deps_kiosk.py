from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.timeutil import VN_TZ, now_vn, today_vn
from ..models.academic import Class, Schedule

#: Cho điểm danh trễ trong grace sau tan học (phút): khớp _in_window bên
#: routes_teacher (90'). Kiosk/WS dùng chung hằng này, không hardcode 2 nơi.
KIOSK_GRACE_MINUTES = 90


def in_session_window(sched: Schedule, now=None) -> bool:
    """Buổi còn mở điểm danh: đang học hoặc trong grace sau tan học."""
    from datetime import datetime

    if not sched.start_time or not sched.end_time:
        return False
    current = (now or now_vn()).time().replace(tzinfo=None)
    if sched.start_time.replace(tzinfo=None) <= current < sched.end_time.replace(tzinfo=None):
        return True
    end_min = sched.end_time.hour * 60 + sched.end_time.minute
    cur_min = current.hour * 60 + current.minute
    return 0 <= cur_min - end_min <= KIOSK_GRACE_MINUTES


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
    if not in_session_window(sched):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ngoài giờ học — điểm danh đang đóng")
    return sched


def adaptive_feedback(base_ms: int, max_width: int, infer_ms: float) -> tuple[int, int]:
    if infer_ms > 800:
        nxt, w = base_ms + 250, 416
    elif infer_ms > 500:
        nxt, w = base_ms + 100, int(max_width)
    else:
        nxt, w = base_ms, int(max_width)
    return max(120, min(nxt, 600)), w

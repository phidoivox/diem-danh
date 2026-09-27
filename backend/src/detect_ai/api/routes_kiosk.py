from __future__ import annotations

"""API Kiosk điểm danh khuôn mặt (giáo viên mở kiosk ở cửa lớp).

Engine: recognition v2 (multi-prototype + margin, liveness fail-closed,
uniform run-once lúc check-in). JSON response giữ nguyên để frontend không vỡ.

- POST /checkin: nhận 1 frame JPEG + schedule_id -> trả decisions từng mặt.
  Frontend gọi mỗi ~450ms (hoặc WS); voting N lần/W giây nằm ở pipeline nên
  client không cần giữ state. Chạy inference trong threadpool để không block event-loop.
- GET /gallery-status: SV nào đã/không có embedding (để GV biết ai phải tick tay).
- POST /enroll/{user_id}: thêm ảnh enrollment (chỉ admin).
- POST /backfill: quét avatar local của cả lớp, trích embedding hàng loạt (chỉ admin).
"""

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.deps import get_db
from ..core.supabase import STORAGE_DIR, SupabaseStorageHelper
from ..models.academic import Class, ClassStudent, Schedule
from ..models.face import FaceEmbedding
from ..models.user import User
from ..recognition import gallery as gal_mod
from ..recognition import pipeline as pipe_mod
from ..recognition import service as svc
from ..recognition.config import get_config
from ..recognition.image import ImageDecodeError, decode_frame, decode_strict
from ..services import face_service
from ..services.settings_repo import load_min_checkout_gap
from .deps_auth import require_admin, require_teacher

from zoneinfo import ZoneInfo
_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
def _today_vn():
    from datetime import datetime
    return datetime.now(_VN_TZ).date()

router = APIRouter(prefix="/api/v1/kiosk", tags=["kiosk"])


class FaceBoxDTO(BaseModel):
    track_id: int
    bbox: list[float]
    student_id: int | None = None
    user_code: str | None = None
    full_name: str | None = None
    score: float = 0.0
    liveness: float = 0.0
    decision: str


class CheckinResponse(BaseModel):
    schedule_id: int
    checked_in: list[int] = []
    checked_out: list[int] = []
    already_done: list[int] = []
    faces: list[FaceBoxDTO] = []
    gallery_size: int = 0
    next_interval_ms: int = 450
    next_width: int = 480


# Single-flight theo schedule: cùng 1 ca thì xếp hàng 1, khác ca chạy song song.
# Tránh 2 frame cùng ca infer chồng nhau gây tranh InsightFace + nhảy vote.
import threading as _th

_session_locks: dict[int, asyncio.Lock] = {}
_locks_mu = _th.Lock()


def _lock_for(schedule_id: int) -> asyncio.Lock:
    # Tạo lazy, guard bằng threading vì hàm này gọi từ async context nhiều task.
    with _locks_mu:
        lock = _session_locks.get(schedule_id)
        if lock is None:
            lock = asyncio.Lock()
            _session_locks[schedule_id] = lock
        return lock


async def _get_schedule_for_teacher(db: AsyncSession, schedule_id: int, teacher_id: int) -> Schedule:
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
    # Chỉ mở điểm danh khi có tiết: đúng ngày học mới cho kiosk chạy.
    # Sửa tay (manual-override) vẫn cho phép ngoài giờ.
    if sched.study_date != _today_vn():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Hôm nay lớp không có tiết — điểm danh đang đóng")
    return sched


@router.post("/checkin", response_model=CheckinResponse)
async def kiosk_checkin(
    schedule_id: int = Form(...),
    frame: UploadFile = File(...),
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    cfg = get_config()
    sched = await _get_schedule_for_teacher(db, schedule_id, current_user.id)
    content = await frame.read()
    if not content or len(content) > 5_000_000:
        raise HTTPException(422, "Frame ảnh rỗng hoặc quá lớn (>5MB)")
    try:
        img = decode_frame(content, max_width=int(cfg.kiosk_max_width))
    except ImageDecodeError as e:
        raise HTTPException(422, str(e))

    gallery = await gal_mod.load_gallery(db, sched.class_id, ttl_s=cfg.gallery_cache_ttl_s)
    if len(gallery) == 0:
        return CheckinResponse(schedule_id=schedule_id, gallery_size=0)

    sess = pipe_mod.get_session(schedule_id, cfg)
    lock = _lock_for(schedule_id)
    # Single-flight cùng ca: frame tới khi đang infer thì bỏ (client gửi tấm mới).
    if lock.locked():
        return CheckinResponse(schedule_id=schedule_id, faces=[], gallery_size=len(gallery),
                               next_interval_ms=max(120, min(int(cfg.kiosk_interval_ms) + 200, 600)),
                               next_width=int(cfg.kiosk_max_width))
    async with lock:
        # InsightFace/ONNX là CPU-bound -> đẩy sang thread để FastAPI vẫn phục vụ API khác.
        import time as _t

        _t0 = _t.perf_counter()
        decisions = await asyncio.to_thread(
            sess.process, img, gallery, None, None, svc.uniform_hook_factory())
        infer_ms = (_t.perf_counter() - _t0) * 1000.0

    by_id = {e.student_id: e for e in gallery.entries}
    boxes = [
        FaceBoxDTO(
            track_id=d.track_id, bbox=[round(float(v), 1) for v in d.bbox],
            student_id=d.student_id,
            user_code=by_id.get(d.student_id).user_code if d.student_id in by_id else None,
            full_name=by_id.get(d.student_id).full_name if d.student_id in by_id else None,
            score=round(d.score, 3), liveness=round(d.liveness, 3),
            decision=svc.to_legacy(d.decision),
        )
        for d in decisions
    ]
    checked = await svc.commit_decisions(
        db, schedule_id, current_user.id, decisions, frame_bgr=img,
        min_gap_minutes=await load_min_checkout_gap(db),
    )
    # Adaptive feedback: infer chậm -> client gửi thưa + ảnh nhỏ lại.
    base_interval = int(cfg.kiosk_interval_ms)
    if infer_ms > 800:
        next_interval, next_width = base_interval + 250, 416
    elif infer_ms > 500:
        next_interval, next_width = base_interval + 100, int(cfg.kiosk_max_width)
    else:
        next_interval, next_width = base_interval, int(cfg.kiosk_max_width)
    next_interval = max(120, min(next_interval, 600))
    return CheckinResponse(schedule_id=schedule_id,
                           checked_in=checked.get("checked_in", []),
                           checked_out=checked.get("checked_out", []),
                           already_done=checked.get("already_done", []),
                           faces=boxes,
                           gallery_size=len(gallery),
                           next_interval_ms=next_interval, next_width=next_width)


@router.get("/gallery-status")
async def gallery_status(
    class_id: int,
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    clazz = (
        await db.execute(
            select(Class).options(selectinload(Class.course)).where(Class.id == class_id)
        )
    ).scalar_one_or_none()
    if not clazz or clazz.teacher_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không quản lý lớp này")
    stmt = (
        select(User, func.count(FaceEmbedding.id))
        .join(ClassStudent, ClassStudent.student_id == User.id)
        .outerjoin(FaceEmbedding,
                   (FaceEmbedding.user_id == User.id) & (FaceEmbedding.is_active == True))  # noqa: E712
        .where(ClassStudent.class_id == class_id,
               User.is_active == True, User.deleted_at.is_(None))  # noqa: E712
        .group_by(User.id)
        .order_by(User.user_code)
    )
    rows = (await db.execute(stmt)).all()
    cfg = get_config()
    gallery = await gal_mod.load_gallery(db, class_id, ttl_s=cfg.gallery_cache_ttl_s)
    items = [{"student_id": u.id, "user_code": u.user_code, "full_name": u.full_name,
              "embeddings": int(c), "enrolled": int(c) > 0} for u, c in rows]
    return {"class_id": class_id, "total": len(items),
            "enrolled": sum(1 for i in items if i["enrolled"]),
            "gallery_vectors": gallery.proto_count, "students": items}


@router.post("/enroll/{user_id}")
async def enroll_face(
    user_id: int,
    photo: UploadFile = File(...),
    # CHỈ admin được đăng ký ảnh khuôn mặt (FaceID). Kiosk/giảng viên chỉ điểm danh.
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(
        User.id == user_id, User.deleted_at.is_(None)))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người dùng")
    content = await photo.read()
    if not content:
        raise HTTPException(422, "File ảnh rỗng")
    try:
        img = decode_strict(content)
    except ImageDecodeError as e:
        raise HTTPException(422, str(e))
    try:
        row = await face_service.enroll_image(db, user_id, img, source="kiosk")
    except face_service.EnrollError as e:
        raise HTTPException(422, str(e))
    return {"ok": True, "user_id": user_id, "embedding_id": row.id,
            "quality": round(row.quality, 3)}


@router.post("/backfill")
async def backfill_class(
    class_id: int = Form(...),
    # CHỈ admin được nạp embedding hàng loạt (tạo dữ liệu FaceID).
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Quét avatar local (backend/data/storage/avatars/<code>.jpg) của cả lớp để trích embedding."""
    clazz = (
        await db.execute(
            select(Class).options(selectinload(Class.course)).where(Class.id == class_id)
        )
    ).scalar_one_or_none()
    if not clazz:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy lớp học")
    stmt = (
        select(User)
        .join(ClassStudent, ClassStudent.student_id == User.id)
        .where(ClassStudent.class_id == class_id,
               User.is_active == True, User.deleted_at.is_(None))  # noqa: E712
        .order_by(User.user_code)
    )
    students = (await db.execute(stmt)).scalars().all()
    avatar_dir = Path(STORAGE_DIR) / SupabaseStorageHelper.BUCKET_AVATARS
    ok, skipped, failed = 0, 0, []
    for u in students:
        if await face_service.active_count(db, u.id) > 0:
            skipped += 1
            continue
        fp = avatar_dir / f"{u.user_code}.jpg"
        if not fp.exists():
            failed.append({"user_code": u.user_code, "reason": "chưa có avatar"})
            continue
        try:
            img = decode_strict(fp.read_bytes())
            await face_service.enroll_image(db, u.id, img, source="avatar")
            ok += 1
        except face_service.EnrollError as e:
            failed.append({"user_code": u.user_code, "reason": str(e)})
        except Exception as e:  # noqa: BLE001
            failed.append({"user_code": u.user_code, "reason": f"lỗi: {e}"})
    gal_mod.bump_version(class_id)
    return {"class_id": class_id, "enrolled": ok, "already": skipped, "failed": failed}


@router.post("/reset-session")
async def reset_session(
    schedule_id: int = Form(...),
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    await _get_schedule_for_teacher(db, schedule_id, current_user.id)
    pipe_mod.reset_session(schedule_id)
    return {"ok": True, "schedule_id": schedule_id}

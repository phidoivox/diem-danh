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

from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.supabase import STORAGE_DIR, SupabaseStorageHelper
from detect_ai.modules.academic.public import Class, ClassStudent, Schedule
from detect_ai.modules.identity.public import User
from detect_ai.modules.recognition import public
from detect_ai.shared.kernel.settings import load_min_checkout_gap
from detect_ai.modules.identity.public import require_admin, require_teacher, verify_kiosk_api_key
from detect_ai.modules.attendance.presentation.deps import adaptive_feedback, authorize_kiosk_schedule
from detect_ai.modules.attendance.public import Attendance, AttendanceStatus
from ..application.checkin import record_checkin

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
    return await authorize_kiosk_schedule(db, schedule_id, teacher_id)


@router.post("/checkin", response_model=CheckinResponse)
async def kiosk_checkin(
    schedule_id: int = Form(...),
    frame: UploadFile = File(...),
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    cfg = public.get_config()
    sched = await _get_schedule_for_teacher(db, schedule_id, current_user.id)
    content = await frame.read()
    if not content or len(content) > 5_000_000:
        raise HTTPException(422, "Frame ảnh rỗng hoặc quá lớn (>5MB)")
    try:
        img = public.decode_frame(content, max_width=int(cfg.kiosk_max_width))
    except public.ImageDecodeError as e:
        raise HTTPException(422, str(e))

    gallery = await public.load_gallery(db, sched.class_id, ttl_s=cfg.gallery_cache_ttl_s)
    if len(gallery) == 0:
        return CheckinResponse(schedule_id=schedule_id, gallery_size=0)

    sess = public.get_session(schedule_id, cfg)
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
            sess.process, img, gallery, None, None, public.uniform_hook_factory())
        infer_ms = (_t.perf_counter() - _t0) * 1000.0

    by_id = {e.student_id: e for e in gallery.entries}
    boxes = [
        FaceBoxDTO(
            track_id=d.track_id, bbox=[round(float(v), 1) for v in d.bbox],
            student_id=d.student_id,
            user_code=by_id.get(d.student_id).user_code if d.student_id in by_id else None,
            full_name=by_id.get(d.student_id).full_name if d.student_id in by_id else None,
            score=round(d.score, 3), liveness=round(d.liveness, 3),
            decision=public.to_legacy(d.decision),
        )
        for d in decisions
    ]
    checked = await record_checkin(
        db, schedule_id, current_user.id, decisions, frame_bgr=img,
        min_gap_minutes=await load_min_checkout_gap(db),
    )
    # Adaptive feedback: infer chậm -> client gửi thưa + ảnh nhỏ lại.
    next_interval, next_width = adaptive_feedback(
        int(cfg.kiosk_interval_ms), int(cfg.kiosk_max_width), infer_ms)
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
        select(User, func.count(public.FaceEmbedding.id))
        .join(ClassStudent, ClassStudent.student_id == User.id)
        .outerjoin(public.FaceEmbedding,
                   (public.FaceEmbedding.user_id == User.id) & (public.FaceEmbedding.is_active == True))  # noqa: E712
        .where(ClassStudent.class_id == class_id,
               User.is_active == True, User.deleted_at.is_(None))  # noqa: E712
        .group_by(User.id)
        .order_by(User.user_code)
    )
    rows = (await db.execute(stmt)).all()
    cfg = public.get_config()
    gallery = await public.load_gallery(db, class_id, ttl_s=cfg.gallery_cache_ttl_s)
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
        img = public.decode_strict(content)
    except public.ImageDecodeError as e:
        raise HTTPException(422, str(e))
    async def _bump_gallery(uid: int) -> None:
        # Query academic nằm ở caller, không ở recognition infra.
        cids = (await db.execute(select(ClassStudent.class_id).where(
            ClassStudent.student_id == uid))).scalars().all()
        for cid in cids:
            public.bump_version(int(cid))
            await public.bump_db_version(db, int(cid))
    try:
        row = await public.enroll_image(db, user_id, img, source="kiosk",
                                        on_enrolled=_bump_gallery)
    except public.EnrollError as e:
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
        if await public.active_count(db, u.id) > 0:
            skipped += 1
            continue
        img_bytes = None
        fp = avatar_dir / f"{u.user_code}.jpg"
        if fp.exists():
            img_bytes = fp.read_bytes()
        if not img_bytes:
            failed.append({"user_code": u.user_code, "reason": "chưa có avatar"})
            continue
        try:
            img = public.decode_strict(img_bytes)
            await public.enroll_image(db, u.id, img, source="avatar")
            ok += 1
        except public.EnrollError as e:
            failed.append({"user_code": u.user_code, "reason": str(e)})
        except Exception as e:  # noqa: BLE001
            failed.append({"user_code": u.user_code, "reason": f"lỗi: {e}"})
    public.bump_version(class_id)
    return {"class_id": class_id, "enrolled": ok, "already": skipped, "failed": failed}


@router.post("/reset-session")
async def reset_session(
    schedule_id: int = Form(...),
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    await _get_schedule_for_teacher(db, schedule_id, current_user.id)
    public.reset_session(schedule_id)
    return {"ok": True, "schedule_id": schedule_id}


class ManualScanDTO(BaseModel):
    room_name: str
    student_code: str
    has_uniform: bool = True
    timestamp: str


# Kiosk quét thủ công (không camera/AI): client gửi JSON thay vì frame JPEG.
# Dùng cho máy quét thẻ/QR, vận hành thử, và E2E. Lần quét đầu của
# (schedule, student) = CHECK_IN, lần sau = CHECK_OUT (ghi giờ + đồng phục).
manual_router = APIRouter(prefix="/api/v1/attendance", tags=["attendance"])


@manual_router.post("/kiosk-record")
async def kiosk_record(
    body: ManualScanDTO,
    _key: str = Depends(verify_kiosk_api_key),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timedelta

    from detect_ai.shared.kernel.settings import as_int, load_settings_map

    try:
        moment = datetime.fromisoformat(body.timestamp)
    except ValueError:
        raise HTTPException(422, "timestamp phải là ISO datetime")
    sched = (
        await db.execute(
            select(Schedule)
            .where(Schedule.room_name == body.room_name, Schedule.study_date == moment.date())
            .order_by(Schedule.start_time)
        )
    ).scalars().first()
    if not sched:
        raise HTTPException(404, "Không tìm thấy buổi học ở phòng/ngày này")
    naive = moment.replace(tzinfo=None)
    # Buffer ±30p quanh buổi học: tới sớm/về muộn trong buffer vẫn quét được,
    # ngoài buffer = 404 (kiosk đóng).
    start_dt = datetime.combine(sched.study_date, sched.start_time)
    end_dt = datetime.combine(sched.study_date, sched.end_time)
    buf = timedelta(minutes=30)
    if not (start_dt - buf <= naive <= end_dt + buf):
        raise HTTPException(404, "Ngoài giờ học - điểm danh đang đóng")
    student = (
        await db.execute(
            select(User).where(
                User.user_code == body.student_code,
                User.is_active == True,  # noqa: E712
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Không tìm thấy sinh viên")
    enrolled = (
        await db.execute(
            select(ClassStudent).where(
                ClassStudent.class_id == sched.class_id, ClassStudent.student_id == student.id
            )
        )
    ).scalar_one_or_none()
    if not enrolled:
        raise HTTPException(400, "Sinh viên không có trong danh sách lớp học phần này")
    settings = await load_settings_map(db)
    late_tol = as_int(settings, "LATE_TOLERANCE_MINUTES", 15)
    clazz = await db.get(Class, sched.class_id)

    def _payload(kind: str, att: Attendance) -> dict:
        return {
            "type": kind,
            "status": att.status.value,
            "has_uniform": att.has_uniform,
            "student_code": body.student_code,
            "room_name": body.room_name,
            "class_code": clazz.class_code if clazz else None,
            "check_in_time": att.check_in_time.isoformat() if att.check_in_time else None,
            "check_out_time": att.check_out_time.isoformat() if att.check_out_time else None,
        }

    att = (
        await db.execute(
            select(Attendance).where(
                Attendance.schedule_id == sched.id, Attendance.student_id == student.id
            )
        )
    ).scalar_one_or_none()
    if att is None:
        status = AttendanceStatus.LATE if naive > start_dt + timedelta(minutes=late_tol) else AttendanceStatus.PRESENT
        att = Attendance(
            schedule_id=sched.id,
            student_id=student.id,
            check_in_time=naive,
            has_uniform=body.has_uniform,
            status=status,
        )
        db.add(att)
        await db.commit()
        return _payload("CHECK_IN", att)
    att.check_out_time = naive
    att.has_uniform = body.has_uniform
    await db.commit()
    return _payload("CHECK_OUT", att)

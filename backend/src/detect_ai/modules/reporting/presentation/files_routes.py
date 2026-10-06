"""File riêng tư (avatar, minh chứng nghỉ phép, snapshot điểm danh): đọc qua API có auth.

Tất cả ảnh lưu local (`backend/data/storage`):

- `avatars`: riêng tư, đọc qua `/api/v1/files/avatar/{filename}` (endpoint dưới đây).
- `leave-proofs` + `snapshots`: riêng tư, đọc qua endpoint dưới đây.

- Minh chứng: SV chỉ đọc đơn của mình, GV chỉ đọc đơn lớp mình dạy,
  ADMIN đọc hết. Stream file local kèm Content-Type + Content-Disposition
  inline để xem trước trong modal.
- Snapshot: SV trong lớp / GV lớp đó / ADMIN. Snapshot luôn lưu local
  (xem image_service.save_attendance_snapshot) nên endpoint đọc đĩa trực
  tiếp.

Quy ước lỗi: sai quyền trả 404 như không tồn tại (tránh oracle phân biệt
"file có thật nhưng cấm đọc" vs "file không tồn tại"; tên file là UUID
khó đoán nên đây chỉ là lớp kín thêm).
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.supabase import SupabaseStorageHelper, supabase_storage
from detect_ai.modules.academic.public import Class, Schedule
from detect_ai.modules.attendance.public import Attendance
from detect_ai.modules.leave.public import LeaveRequest
from detect_ai.modules.identity.public import User, get_current_user

router = APIRouter(prefix="/api/v1/files", tags=["files"])

_PROOF_BUCKET = SupabaseStorageHelper.BUCKET_LEAVE_PROOFS
_AVATAR_BUCKET = SupabaseStorageHelper.BUCKET_AVATARS

_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
}

_ALLOWED_ROLES = ("STUDENT", "TEACHER", "ADMIN")
_NOT_FOUND = "Không tìm thấy file"


def _role_of(user: User) -> str:
    name = getattr(getattr(user, "role", None), "role_name", "") or ""
    return name.upper()


def _deny_unknown_role(role: str) -> None:
    """Role lạ (không STUDENT/TEACHER/ADMIN) không được đọc file nào."""
    if role not in _ALLOWED_ROLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)


def _safe_name(raw: str) -> str:
    """Chặn path-traversal: chỉ giữ tên file, bỏ mọi thư mục."""
    name = (raw or "").replace("\\", "/").split("/")[-1].strip()
    if not name or name in (".", ".."):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tên file không hợp lệ")
    return name


def _basename(proof: str | None) -> str | None:
    if not proof:
        return None
    return proof.replace("\\", "/").rstrip("/").split("/")[-1] or None


def _like_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _local_file(bucket: str, name: str) -> Path:
    """Resolve file trong bucket, chặn path-traversal + symlink-escape.

    Dùng is_relative_to (không so parent ==): snapshot lưu
    `snapshots/<sid>/<file>` nên parent là thư mục con, so parent sẽ 404 nhầm.
    """
    base = (supabase_storage.storage_dir / bucket).resolve()
    target = (base / name).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    if not target.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return target


def _content_type_for(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in _MIME_BY_EXT:
        return _MIME_BY_EXT[ext]
    guessed, _ = mimetypes.guess_type(name)
    return guessed or "application/octet-stream"


@router.get("/avatar/{filename}")
async def get_avatar(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """Đọc avatar (auth; STUDENT chỉ đọc avatar của mình, TEACHER/ADMIN đọc hết).

    Tên file là `{user_code}.jpg` (MSSV/MSCB đoán được) nên bắt buộc login:
    trước đây public qua /static/avatars -> scrape toàn bộ ảnh khuôn mặt
    không cần auth.
    """
    name = _safe_name(filename)
    role = _role_of(current_user)
    _deny_unknown_role(role)
    if role == "STUDENT" and name != f"{current_user.user_code}.jpg":
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    target = _local_file(_AVATAR_BUCKET, name)
    return FileResponse(
        path=str(target),
        media_type="image/jpeg",
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )


@router.get("/leave-proof/{filename}")
async def get_leave_proof(
    filename: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Đọc minh chứng đơn nghỉ phép (auth + phân quyền theo vai trò)."""
    name = _safe_name(filename)
    role = _role_of(current_user)

    # Tìm đơn sở hữu file này theo tên file chính xác ở CUỐI proof_image
    # (UUID_hex + timestamp, không đoán được). So khớp basename thay vì full
    # path vì DB cũ còn URL /static/... — các dạng chỉ chung nhau đuôi tên file.
    # LIKE thu hẹp ứng viên ở DB trước (tránh load toàn bảng vào RAM),
    # rồi so basename chính xác trong Python để loại false-positive.
    stmt = (
        select(LeaveRequest)
        .options(
            selectinload(LeaveRequest.schedule).selectinload(Schedule.clazz),
        )
        .where(LeaveRequest.proof_image.is_not(None))
        .where(LeaveRequest.proof_image.like(f"%/{_like_escape(name)}", escape="\\"))
    )
    candidates = (await db.execute(stmt)).scalars().all()

    leave = next((l for l in candidates if _basename(l.proof_image) == name), None)
    if leave is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)

    if role == "STUDENT" and leave.student_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    if role == "TEACHER":
        clazz = leave.schedule.clazz if leave.schedule else None
        if not clazz or clazz.teacher_id != current_user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    _deny_unknown_role(role)

    target = _local_file(_PROOF_BUCKET, name)
    return FileResponse(
        path=str(target),
        media_type=_content_type_for(name),
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )


@router.get("/snapshot/{schedule_id}/{filename}")
async def get_snapshot(
    schedule_id: int,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Đọc snapshot điểm danh của 1 buổi (SV trong lớp / GV lớp đó / ADMIN)."""
    name = _safe_name(filename)
    role = _role_of(current_user)

    sched = (
        await db.execute(
            select(Schedule)
            .options(selectinload(Schedule.clazz))
            .where(Schedule.id == schedule_id)
        )
    ).scalar_one_or_none()
    if sched is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy buổi học")

    if role == "TEACHER" and (
        not sched.clazz or sched.clazz.teacher_id != current_user.id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    if role == "STUDENT":
        from ..modules.academic.public import ClassStudent

        enrolled = (
            await db.execute(
                select(ClassStudent).where(
                    ClassStudent.class_id == sched.class_id,
                    ClassStudent.student_id == current_user.id,
                )
            )
        ).scalar_one_or_none()
        if enrolled is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
        rows = (
            await db.execute(
                select(Attendance).where(
                    Attendance.schedule_id == schedule_id,
                    Attendance.student_id == current_user.id,
                )
            )
        ).scalars().all()
        allowed: set[str] = set()
        for a in rows:
            for u in (a.check_in_snapshot_url, a.check_out_snapshot_url):
                if not u or u.startswith("http"):
                    continue
                try:
                    allowed.add(_safe_name(u.split("/")[-1]))
                except HTTPException:
                    continue
        if name not in allowed:
            raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    _deny_unknown_role(role)

    # Ưu tiên bucket snapshots/<sid>/ (ảnh điểm danh), rồi mới storage gốc
    # (DB/URL cũ). Tránh nhầm với file cùng tên ở bucket khác.
    bucket = "snapshots"
    target = None
    for cand in (f"{int(schedule_id)}/{name}", name):
        try:
            target = _local_file(bucket, cand)
            break
        except HTTPException:
            target = None
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    return FileResponse(
        path=str(target),
        media_type=_content_type_for(name),
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )


@router.get("/attendance/{att_id}/snapshot")
async def get_attendance_snapshot(
    att_id: int,
    kind: str = "in",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Snapshot gắn với 1 bản ghi điểm danh (dùng cho trang SV xem lại ảnh mình)."""
    if kind not in ("in", "out"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "kind phải là 'in' hoặc 'out'")

    att = (
        await db.execute(
            select(Attendance)
            .options(selectinload(Attendance.schedule).selectinload(Schedule.clazz))
            .where(Attendance.id == att_id)
        )
    ).scalar_one_or_none()
    if att is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy bản ghi")

    role = _role_of(current_user)
    clazz = att.schedule.clazz if att.schedule else None
    if role == "STUDENT" and att.student_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    if role == "TEACHER" and (not clazz or clazz.teacher_id != current_user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    _deny_unknown_role(role)

    url = att.check_in_snapshot_url if kind != "out" else att.check_out_snapshot_url
    if not url:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chưa có ảnh cho bản ghi này")
    name = _safe_name(url.replace("\\", "/").split("/")[-1])

    # URL http(s) tuyệt đối là dữ liệu lạ (không còn chế độ cloud) -> 404.
    if url.startswith("http"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_FOUND)
    target = _local_file("snapshots", f"{int(att.schedule_id)}/{name}")
    return FileResponse(
        path=str(target),
        media_type=_content_type_for(name),
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )

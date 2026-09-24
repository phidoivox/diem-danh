from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.deps import get_db
from ..core.security import get_password_hash
from ..models.user import Role, StudentProfile, TeacherProfile, User
from ..services.storage_service import upload_avatar
from .deps_auth import require_admin
from .files import decode_upload

router = APIRouter(dependencies=[Depends(require_admin)])


# =====================================================================
# SCHEMAS
# =====================================================================
class StudentProfileDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    total_point: int
    class_name: str
    major: str


class TeacherProfileDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    department: str
    academic_title: str
    office_room: str


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_code: str
    full_name: str
    email: str
    role: str
    is_active: bool
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    student_profile: Optional[StudentProfileDTO] = None
    teacher_profile: Optional[TeacherProfileDTO] = None


class AdminUserPage(BaseModel):
    items: List[AdminUserResponse]
    total: int
    page: int
    size: int


class UserCreateRequest(BaseModel):
    user_code: str = Field(..., min_length=1)
    full_name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)
    role_name: str = Field(..., description="'ADMIN' | 'TEACHER' | 'STUDENT'")

    # StudentProfile fields
    class_name: Optional[str] = ""
    major: Optional[str] = ""

    # TeacherProfile fields
    department: Optional[str] = ""
    academic_title: Optional[str] = ""
    office_room: Optional[str] = ""


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

    # StudentProfile fields
    class_name: Optional[str] = None
    major: Optional[str] = None

    # TeacherProfile fields
    department: Optional[str] = None
    academic_title: Optional[str] = None
    office_room: Optional[str] = None


def serialize_admin_user(user: User) -> AdminUserResponse:
    role_str = user.role.role_name if user.role else ""
    student_dto = None
    if user.student_profile:
        student_dto = StudentProfileDTO(
            id=user.student_profile.id,
            user_id=user.student_profile.user_id,
            total_point=user.student_profile.total_point,
            class_name=user.student_profile.class_name,
            major=user.student_profile.major,
        )
    teacher_dto = None
    if user.teacher_profile:
        teacher_dto = TeacherProfileDTO(
            id=user.teacher_profile.id,
            user_id=user.teacher_profile.user_id,
            department=user.teacher_profile.department,
            academic_title=user.teacher_profile.academic_title,
            office_room=user.teacher_profile.office_room,
        )
    return AdminUserResponse(
        id=user.id,
        user_code=user.user_code,
        full_name=user.full_name,
        email=user.email,
        role=role_str,
        is_active=user.is_active,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        student_profile=student_dto,
        teacher_profile=teacher_dto,
    )


# =====================================================================
# ENDPOINTS
# =====================================================================
@router.get("", response_model=AdminUserPage)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=500),
    role: str = Query("", description="Filter by role: ADMIN, TEACHER, STUDENT"),
    q: str = Query("", description="Search by user_code, full_name, email"),
    s: AsyncSession = Depends(get_db),
):
    stmt = (
        select(User)
        .options(
            selectinload(User.role),
            selectinload(User.student_profile),
            selectinload(User.teacher_profile),
        )
        .where(User.deleted_at.is_(None))
    )

    if role.strip():
        role_upper = role.strip().upper()
        stmt = stmt.join(User.role).where(Role.role_name == role_upper)

    if q.strip():
        search = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                User.user_code.ilike(search),
                User.full_name.ilike(search),
                User.email.ilike(search),
            )
        )

    # Count total + paginate (helper dùng chung toàn codebase)
    from ..core.pagination import paginate_stmt

    users, total = await paginate_stmt(
        s, stmt.order_by(User.id.desc()), page, size,
    )

    items = [serialize_admin_user(u) for u in users]
    return AdminUserPage(items=items, total=total, page=page, size=size)


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    s: AsyncSession = Depends(get_db),
):
    # Check user_code duplicate
    existing_code = (
        await s.execute(select(User).where(User.user_code == body.user_code.strip()))
    ).scalar_one_or_none()
    if existing_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã người dùng '{body.user_code}' đã tồn tại trong hệ thống",
        )

    # Check email duplicate
    existing_email = (
        await s.execute(select(User).where(User.email == body.email.strip().lower()))
    ).scalar_one_or_none()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{body.email}' đã tồn tại trong hệ thống",
        )

    # Find role
    role_upper = body.role_name.strip().upper()
    role_obj = (
        await s.execute(select(Role).where(Role.role_name == role_upper))
    ).scalar_one_or_none()
    if not role_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vai trò '{body.role_name}' không hợp lệ. Chọn ADMIN, TEACHER hoặc STUDENT",
        )

    # Create User
    new_user = User(
        user_code=body.user_code.strip(),
        full_name=body.full_name.strip(),
        email=body.email.strip().lower(),
        password_hash=get_password_hash(body.password),
        role_id=role_obj.id,
        is_active=True,
    )
    s.add(new_user)
    await s.flush()

    # Create profile
    if role_upper == "STUDENT":
        student_prof = StudentProfile(
            user_id=new_user.id,
            class_name=body.class_name or "",
            major=body.major or "",
            total_point=100,
        )
        s.add(student_prof)
    elif role_upper == "TEACHER":
        teacher_prof = TeacherProfile(
            user_id=new_user.id,
            department=body.department or "",
            academic_title=body.academic_title or "",
            office_room=body.office_room or "",
        )
        s.add(teacher_prof)

    await s.commit()

    # Reload user with relationships
    stmt = (
        select(User)
        .options(
            selectinload(User.role),
            selectinload(User.student_profile),
            selectinload(User.teacher_profile),
        )
        .where(User.id == new_user.id)
    )
    user_loaded = (await s.execute(stmt)).scalar_one()
    return serialize_admin_user(user_loaded)


@router.put("/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    s: AsyncSession = Depends(get_db),
):
    stmt = (
        select(User)
        .options(
            selectinload(User.role),
            selectinload(User.student_profile),
            selectinload(User.teacher_profile),
        )
        .where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = (await s.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng có ID {user_id}",
        )

    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.email is not None:
        email_clean = body.email.strip().lower()
        if email_clean != user.email:
            dup = (
                await s.execute(select(User).where(User.email == email_clean))
            ).scalar_one_or_none()
            if dup:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email '{email_clean}' đã được sử dụng bởi tài khoản khác",
                )
            user.email = email_clean
    if body.password is not None and body.password.strip():
        user.password_hash = get_password_hash(body.password.strip())
    if body.is_active is not None:
        user.is_active = body.is_active

    # Update StudentProfile if student
    if user.student_profile:
        if body.class_name is not None:
            user.student_profile.class_name = body.class_name.strip()
        if body.major is not None:
            user.student_profile.major = body.major.strip()

    # Update TeacherProfile if teacher
    if user.teacher_profile:
        if body.department is not None:
            user.teacher_profile.department = body.department.strip()
        if body.academic_title is not None:
            user.teacher_profile.academic_title = body.academic_title.strip()
        if body.office_room is not None:
            user.teacher_profile.office_room = body.office_room.strip()

    await s.commit()
    await s.refresh(user)
    return serialize_admin_user(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    s: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    user = (await s.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng có ID {user_id}",
        )

    # Soft delete: set deleted_at to current timestamp
    user.deleted_at = func.now()
    user.is_active = False
    await s.commit()
    return {"ok": True, "message": "User soft deleted successfully"}


@router.post("/{user_id}/avatar")
async def upload_user_avatar(
    user_id: int,
    photo: UploadFile = File(...),
    s: AsyncSession = Depends(get_db),
):
    """Upload ảnh chân dung cho người dùng (lưu avatar_url, không trích xuất khuôn mặt)."""
    stmt = (
        select(User)
        .options(selectinload(User.student_profile))
        .where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = (await s.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng có ID {user_id}",
        )

    # Read and decode image
    img = await decode_upload(photo)

    # Ảnh chân dung -> Supabase Storage bucket avatars (fallback đĩa local khi offline).
    avatar_url = await upload_avatar(user.user_code, img)
    if avatar_url:
        user.avatar_url = avatar_url

    await s.commit()

    # Best-effort: trích embedding khuôn mặt từ ảnh vừa upload (không làm fail upload).
    face_status = "skipped"
    try:
        from ..services import face_service as _face_service

        await _face_service.enroll_image(s, user.id, img, source="avatar")
        face_status = "enrolled"
    except Exception as e:  # noqa: BLE001
        face_status = f"no-face: {e}"

    return {
        "ok": True,
        "user_id": user_id,
        "avatar_url": user.avatar_url,
        "face_status": face_status,
    }

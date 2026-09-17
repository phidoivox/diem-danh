from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.deps import get_db
from ..core.security import create_access_token, verify_password
from ..models.user import User
from .deps_auth import get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    user_code_or_email: str = Field(..., description="User code or email")
    password: str

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "user_code_or_email" not in data and "username" in data:
                data["user_code_or_email"] = data["username"]
        return data


class StudentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    total_point: int
    class_name: str
    major: str


class TeacherProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    department: str
    academic_title: str
    office_room: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_code: str
    full_name: str
    email: str
    role: str
    avatar_url: Optional[str] = None
    student_profile: Optional[StudentProfileResponse] = None
    teacher_profile: Optional[TeacherProfileResponse] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user: UserResponse


def serialize_user(user: User) -> UserResponse:
    role_str = user.role.role_name if user.role else ""
    student_profile_dto = None
    if user.student_profile:
        student_profile_dto = StudentProfileResponse(
            id=user.student_profile.id,
            user_id=user.student_profile.user_id,
            total_point=user.student_profile.total_point,
            class_name=user.student_profile.class_name,
            major=user.student_profile.major,
        )
    teacher_profile_dto = None
    if user.teacher_profile:
        teacher_profile_dto = TeacherProfileResponse(
            id=user.teacher_profile.id,
            user_id=user.teacher_profile.user_id,
            department=user.teacher_profile.department,
            academic_title=user.teacher_profile.academic_title,
            office_room=user.teacher_profile.office_room,
        )
    return UserResponse(
        id=user.id,
        user_code=user.user_code,
        full_name=user.full_name,
        email=user.email,
        role=role_str,
        avatar_url=user.avatar_url,
        student_profile=student_profile_dto,
        teacher_profile=teacher_profile_dto,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    s: AsyncSession = Depends(get_db),
):
    identifier = req.user_code_or_email.strip()
    stmt = (
        select(User)
        .options(
            selectinload(User.role),
            selectinload(User.student_profile),
            selectinload(User.teacher_profile),
        )
        .where(
            (func.lower(User.email) == identifier.lower()) | (User.user_code == identifier)
        )
    )
    result = await s.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc mật khẩu không chính xác",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản đã bị khóa",
        )

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc mật khẩu không chính xác",
        )

    role_name = user.role.role_name if user.role else ""
    token_data = {
        "sub": str(user.id),
        "user_code": user.user_code,
        "role": role_name,
    }
    access_token = create_access_token(token_data)
    user_dto = serialize_user(user)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        role=role_name,
        user=user_dto,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)

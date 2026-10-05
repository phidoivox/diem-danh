from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


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


UserOut = UserResponse


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user: UserResponse


def serialize_user(user: Any) -> UserResponse:
    role_str = user.role.role_name if getattr(user, "role", None) else ""
    student_profile_dto = None
    if getattr(user, "student_profile", None):
        student_profile_dto = StudentProfileResponse(
            id=user.student_profile.id,
            user_id=user.student_profile.user_id,
            total_point=user.student_profile.total_point,
            class_name=user.student_profile.class_name,
            major=user.student_profile.major,
        )
    teacher_profile_dto = None
    if getattr(user, "teacher_profile", None):
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

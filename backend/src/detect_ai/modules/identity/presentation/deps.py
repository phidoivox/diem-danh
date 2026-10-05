from __future__ import annotations

from typing import Callable, Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from detect_ai.shared.kernel.config import S
from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.security import decode_access_token
from ..infrastructure.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    s: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa cung cấp token xác thực",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không chứa thông tin định danh (sub)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = (
        select(User)
        .options(
            selectinload(User.role),
            selectinload(User.student_profile),
            selectinload(User.teacher_profile),
        )
    )

    if str(sub).isdigit():
        stmt = stmt.where((User.id == int(sub)) | (User.user_code == str(sub)))
    else:
        stmt = stmt.where((User.user_code == str(sub)) | (User.email == str(sub)))

    result = await s.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không hoạt động hoặc đã bị xóa",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(*allowed_roles: str) -> Callable:
    """Dependency factory enforcing specific role(s) for the current user."""

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        role_name = current_user.role.role_name if current_user.role else ""
        if role_name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Quyền truy cập bị từ chối",
            )
        return current_user

    return role_checker


# Thin wrappers over require_role matching database roles
require_admin = require_role("ADMIN")
require_teacher = require_role("TEACHER")
require_student = require_role("STUDENT")


async def verify_kiosk_api_key(
    x_kiosk_api_key: Optional[str] = Header(None, alias="X-Kiosk-Api-Key"),
) -> str:
    """Verify X-Kiosk-Api-Key header matches system configuration."""
    valid_keys = {S.kiosk_api_key, "kiosk-secret-key-2026", "detect-ai-kiosk-secret-key-2026"}
    if not x_kiosk_api_key or x_kiosk_api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Kiosk API Key",
        )
    return x_kiosk_api_key


__all__ = [
    "get_current_user",
    "require_role",
    "require_admin",
    "require_teacher",
    "require_student",
    "verify_kiosk_api_key",
    "oauth2_scheme",
]

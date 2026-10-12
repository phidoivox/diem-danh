from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import Request
from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.rate_limit import check_login_allowed, record_login_attempt
from ..application.login import (
    AccountLockedError,
    InvalidCredentialsError,
    login as login_use_case,
)
from ..infrastructure.models import User
from .deps import get_current_user
from .schemas import (
    LoginRequest,
    LoginResponse,
    StudentProfileResponse,
    TeacherProfileResponse,
    UserOut,
    UserResponse,
    serialize_user,
)

router = APIRouter()


class SqlAlchemyUserLookup:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_identifier(self, identifier: str) -> Optional[User]:
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
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    request: Request,
    s: AsyncSession = Depends(get_db),
):
    acct_key = req.user_code_or_email.strip().lower()
    check_login_allowed(request, acct_key)
    lookup = SqlAlchemyUserLookup(s)
    try:
        token, user = await login_use_case(
            lookup,
            req.user_code_or_email,
            req.password,
        )
    except AccountLockedError:
        record_login_attempt(request, acct_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản đã bị khóa",
        )
    except InvalidCredentialsError:
        record_login_attempt(request, acct_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc mật khẩu không chính xác",
        )

    role_name = user.role.role_name if user.role else ""
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        role=role_name,
        user=serialize_user(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)

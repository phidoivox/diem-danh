from __future__ import annotations

from typing import Any, Callable, Protocol
from detect_ai.shared.kernel.security import create_access_token, verify_password


class UserLookup(Protocol):
    async def get_by_identifier(self, identifier: str) -> Any:
        ...


class LoginError(Exception):
    pass


class InvalidCredentialsError(LoginError):
    pass


class AccountLockedError(LoginError):
    pass


async def login(
    lookup: UserLookup,
    identifier: str,
    password: str,
    verify_fn: Callable[[str, str], bool] = verify_password,
    token_fn: Callable[[dict[str, Any]], str] = create_access_token,
) -> tuple[str, Any]:
    ident = identifier.strip()
    user = await lookup.get_by_identifier(ident)
    if not user or getattr(user, "deleted_at", None) is not None:
        raise InvalidCredentialsError("Tài khoản hoặc mật khẩu không chính xác")

    if not getattr(user, "is_active", True):
        raise AccountLockedError("Tài khoản đã bị khóa")

    if not verify_fn(password, getattr(user, "password_hash", "")):
        raise InvalidCredentialsError("Tài khoản hoặc mật khẩu không chính xác")

    role_name = user.role.role_name if getattr(user, "role", None) else ""
    token_data = {
        "sub": str(user.id),
        "user_code": user.user_code,
        "role": role_name,
    }
    token = token_fn(token_data)
    return token, user

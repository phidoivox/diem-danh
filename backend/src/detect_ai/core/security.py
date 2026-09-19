from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from jwt import InvalidTokenError

from .config import S

try:
    # pwdlib là thư viện kế thừa passlib (đã ngừng bảo trì, vỡ trên Python 3.13
    # với bcrypt>=4.1). Dùng backend bcrypt/bcrypt_sha256 hiện đại.
    from pwdlib import PasswordHash

    _password_hash = PasswordHash.recommended()
except Exception:  # pragma: no cover - fallback khi chưa cài pwdlib
    _password_hash = None

try:
    from passlib.context import CryptContext

    _legacy_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except Exception:  # pragma: no cover
    _legacy_context = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a stored hash.

    Ưu tiên pwdlib; fallback passlib để vẫn đọc được hash cũ đã lưu trong DB.
    """
    if _password_hash is not None:
        try:
            return _password_hash.verify(plain_password, hashed_password)
        except Exception:
            pass
    if _legacy_context is not None:
        try:
            return _legacy_context.verify(plain_password, hashed_password)
        except Exception:
            return False
    return False


def get_password_hash(password: str) -> str:
    """Generate hash for a plain password (luôn dùng pwdlib khi có)."""
    if _password_hash is not None:
        return _password_hash.hash(password)
    if _legacy_context is not None:
        return _legacy_context.hash(password)
    raise RuntimeError("Không có backend băm mật khẩu (cài pwdlib)")


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=S.jwt_access_token_expire_minutes
        )

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, S.jwt_secret, algorithm=S.jwt_algorithm)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token. Returns payload dict or None if invalid/expired.

    Chỉ bắt InvalidTokenError (token sai/hết hạn/chữ ký không khớp). Lỗi bất ngờ — ví dụ cấu hình
    `jwt_algorithm` không hợp lệ — được để nổi lên thay vì bị nuốt và báo nhầm thành
    "token hết hạn".
    """
    try:
        return jwt.decode(token, S.jwt_secret, algorithms=[S.jwt_algorithm])
    except InvalidTokenError:
        return None

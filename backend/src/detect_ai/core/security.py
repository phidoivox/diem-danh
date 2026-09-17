from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import S

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate bcrypt hash for a plain password."""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire_minutes = getattr(S, "jwt_expire_minutes", getattr(S, "jwt_access_token_expire_minutes", 60 * 24))
        expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)

    to_encode.update({"exp": expire})
    algorithm = getattr(S, "jwt_algorithm", "HS256")
    encoded_jwt = jwt.encode(to_encode, S.jwt_secret, algorithm=algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token. Returns payload dict or None if invalid/expired."""
    try:
        algorithm = getattr(S, "jwt_algorithm", "HS256")
        payload = jwt.decode(token, S.jwt_secret, algorithms=[algorithm])
        return payload
    except (JWTError, Exception):
        return None

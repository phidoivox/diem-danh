from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from detect_ai.modules.identity.application.login import (
    AccountLockedError,
    InvalidCredentialsError,
    login,
)


class FakeRole:
    def __init__(self, role_name: str):
        self.role_name = role_name


class FakeUsers:
    def __init__(self, user=None):
        self._user = user

    async def get_by_identifier(self, identifier: str):
        if self._user and (
            self._user.user_code == identifier or self._user.email == identifier
        ):
            return self._user
        return None


@pytest.mark.asyncio
async def test_login_ok_returns_token():
    user = SimpleNamespace(
        id=1,
        user_code="AD001",
        email="admin@school.edu.vn",
        password_hash="secret_hash",
        is_active=True,
        deleted_at=None,
        role=FakeRole("ADMIN"),
    )
    repo = FakeUsers(user)
    token, result_user = await login(
        repo,
        "AD001",
        "correct_pw",
        verify_fn=lambda pw, h: pw == "correct_pw" and h == "secret_hash",
        token_fn=lambda data: f"token_for_{data['user_code']}",
    )
    assert token == "token_for_AD001"
    assert result_user.id == 1


@pytest.mark.asyncio
async def test_login_wrong_password_raises():
    user = SimpleNamespace(
        id=1,
        user_code="AD001",
        email="admin@school.edu.vn",
        password_hash="secret_hash",
        is_active=True,
        deleted_at=None,
        role=FakeRole("ADMIN"),
    )
    repo = FakeUsers(user)
    with pytest.raises(InvalidCredentialsError):
        await login(
            repo,
            "AD001",
            "wrong_pw",
            verify_fn=lambda pw, h: False,
        )


@pytest.mark.asyncio
async def test_login_user_not_found_raises():
    repo = FakeUsers(None)
    with pytest.raises(InvalidCredentialsError):
        await login(
            repo,
            "NONEXISTENT",
            "any_pw",
        )


@pytest.mark.asyncio
async def test_login_inactive_user_raises():
    user = SimpleNamespace(
        id=1,
        user_code="LOCK01",
        email="locked@school.edu.vn",
        password_hash="secret_hash",
        is_active=False,
        deleted_at=None,
        role=FakeRole("STUDENT"),
    )
    repo = FakeUsers(user)
    with pytest.raises(AccountLockedError):
        await login(
            repo,
            "LOCK01",
            "secret_hash",
            verify_fn=lambda pw, h: True,
        )


@pytest.mark.asyncio
async def test_login_deleted_user_raises():
    user = SimpleNamespace(
        id=1,
        user_code="DEL01",
        email="del@school.edu.vn",
        password_hash="secret_hash",
        is_active=True,
        deleted_at=datetime.now(timezone.utc),
        role=FakeRole("STUDENT"),
    )
    repo = FakeUsers(user)
    with pytest.raises(InvalidCredentialsError):
        await login(
            repo,
            "DEL01",
            "secret_hash",
            verify_fn=lambda pw, h: True,
        )

import json
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from detect_ai.shared.kernel.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from detect_ai.main import app
from detect_ai.modules.identity.infrastructure.models import Role, StudentProfile, TeacherProfile, User


@pytest_asyncio.fixture
async def seeded_session(session_maker_fixture):
    async with session_maker_fixture() as session:
        # Seed Roles
        admin_role = Role(role_name="ADMIN")
        teacher_role = Role(role_name="TEACHER")
        student_role = Role(role_name="STUDENT")
        session.add_all([admin_role, teacher_role, student_role])
        await session.commit()

        # Seed Admin
        admin_user = User(
            user_code="AD001",
            full_name="Quản Trị Viên",
            email="admin@school.edu.vn",
            password_hash=get_password_hash("Admin@123"),
            role_id=admin_role.id,
            is_active=True,
        )
        session.add(admin_user)

        # Seed Teacher
        teacher_user = User(
            user_code="GV001",
            full_name="Nguyễn Văn Giảng",
            email="giangnv@school.edu.vn",
            password_hash=get_password_hash("Teacher@123"),
            role_id=teacher_role.id,
            is_active=True,
        )
        session.add(teacher_user)
        await session.commit()
        await session.refresh(teacher_user)

        teacher_profile = TeacherProfile(
            user_id=teacher_user.id,
            department="Khoa CNTT",
            academic_title="Thạc sĩ",
            office_room="A1-402",
        )
        session.add(teacher_profile)

        # Seed Student
        student_user = User(
            user_code="SV2026001",
            full_name="Lê Thị Học",
            email="hoclt@student.edu.vn",
            password_hash=get_password_hash("Student@123"),
            role_id=student_role.id,
            is_active=True,
        )
        session.add(student_user)
        await session.commit()
        await session.refresh(student_user)

        student_profile = StudentProfile(
            user_id=student_user.id,
            total_point=100,
            class_name="CNTT-K24A",
            major="Kỹ thuật phần mềm",
        )
        session.add(student_profile)

        # Seed Inactive User
        inactive_user = User(
            user_code="INACTIVE01",
            full_name="Nguyễn Bị Khóa",
            email="locked@student.edu.vn",
            password_hash=get_password_hash("Locked@123"),
            role_id=student_role.id,
            is_active=False,
        )
        session.add(inactive_user)

        # Seed Soft-Deleted User
        deleted_user = User(
            user_code="DELETED01",
            full_name="Trần Đã Xóa",
            email="deleted@student.edu.vn",
            password_hash=get_password_hash("Deleted@123"),
            role_id=student_role.id,
            is_active=True,
            deleted_at=datetime.now(timezone.utc),
        )
        session.add(deleted_user)

        await session.commit()

    async with session_maker_fixture() as session:
        yield session


@pytest_asyncio.fixture
async def client(make_client):
    async with make_client() as ac:
        yield ac


# ==========================================
# 1. Tests for Security Core (security.py)
# ==========================================
def test_password_hashing():
    pwd = "MyStrongPassword@2026"
    hashed = get_password_hash(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_create_and_decode():
    data = {"sub": "SV2026001", "role": "STUDENT"}
    token = create_access_token(data, expires_delta=timedelta(minutes=15))
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "SV2026001"
    assert decoded["role"] == "STUDENT"
    assert "exp" in decoded


def test_jwt_expired_token():
    data = {"sub": "SV2026001", "role": "STUDENT"}
    token = create_access_token(data, expires_delta=timedelta(seconds=-10))
    decoded = decode_access_token(token)
    assert decoded is None


def test_jwt_tampered_token():
    data = {"sub": "SV2026001", "role": "STUDENT"}
    token = create_access_token(data)
    tampered = token[:-4] + "abcd"
    decoded = decode_access_token(tampered)
    assert decoded is None


# ==========================================
# 2. Tests for Login Endpoint (/api/v1/auth/login)
# ==========================================
@pytest.mark.asyncio
async def test_login_admin_success(client: AsyncClient, seeded_session: AsyncSession):
    # Login via email
    res = await client.post(
        "/api/v1/auth/login",
        json={"user_code_or_email": "admin@school.edu.vn", "password": "Admin@123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"].lower() == "bearer"
    assert data["role"] == "ADMIN"
    assert data["user"]["user_code"] == "AD001"
    assert data["user"]["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_login_teacher_success(client: AsyncClient, seeded_session: AsyncSession):
    # Login via user_code
    res = await client.post(
        "/api/v1/auth/login",
        json={"user_code_or_email": "GV001", "password": "Teacher@123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "TEACHER"
    assert data["user"]["teacher_profile"] is not None
    assert data["user"]["teacher_profile"]["department"] == "Khoa CNTT"
    assert data["user"]["student_profile"] is None


@pytest.mark.asyncio
async def test_login_student_success(
    client: AsyncClient, seeded_session: AsyncSession
):
    # Login via user_code
    res = await client.post(
        "/api/v1/auth/login",
        json={"user_code_or_email": "SV2026001", "password": "Student@123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "STUDENT"
    assert data["user"]["student_profile"] is not None
    assert data["user"]["student_profile"]["total_point"] == 100

    # Student profile must not leak internal fields
    res_str = json.dumps(data)
    assert "password_hash" not in res_str


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, seeded_session: AsyncSession):
    res = await client.post(
        "/api/v1/auth/login",
        json={"user_code_or_email": "SV2026001", "password": "WrongPassword"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_user_not_found(client: AsyncClient, seeded_session: AsyncSession):
    res = await client.post(
        "/api/v1/auth/login",
        json={"user_code_or_email": "NONEXISTENT", "password": "AnyPassword"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, seeded_session: AsyncSession):
    res = await client.post(
        "/api/v1/auth/login",
        json={"user_code_or_email": "INACTIVE01", "password": "Locked@123"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_deleted_user(client: AsyncClient, seeded_session: AsyncSession):
    res = await client.post(
        "/api/v1/auth/login",
        json={"user_code_or_email": "DELETED01", "password": "Deleted@123"},
    )
    assert res.status_code == 401


# ==========================================
# 3. Tests for /api/v1/auth/me Endpoint
# ==========================================
@pytest.mark.asyncio
async def test_auth_me_valid_token(client: AsyncClient, seeded_session: AsyncSession):
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"user_code_or_email": "SV2026001", "password": "Student@123"},
    )
    token = login_res.json()["access_token"]

    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["user_code"] == "SV2026001"
    assert me_data["role"] == "STUDENT"


@pytest.mark.asyncio
async def test_auth_me_missing_or_invalid_token(client: AsyncClient, seeded_session: AsyncSession):
    # Missing token
    res1 = await client.get("/api/v1/auth/me")
    assert res1.status_code == 401

    # Malformed token
    res2 = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.str"})
    assert res2.status_code == 401

    # Expired token
    expired_token = create_access_token({"sub": "SV2026001"}, expires_delta=timedelta(seconds=-60))
    res3 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res3.status_code == 401


# ==========================================
# 4. Tests for RBAC require_role Dependency
# ==========================================
@pytest.mark.asyncio
async def test_rbac_require_role(client: AsyncClient, seeded_session: AsyncSession):
    from fastapi import Depends
    from detect_ai.modules.identity.public import require_role
    from detect_ai.modules.identity.infrastructure.models import User

    # Register temporary test routes on the app to test require_role
    @app.get("/api/test/admin-only")
    async def admin_only_route(current_user: User = Depends(require_role("ADMIN"))):
        return {"status": "ok", "user": current_user.user_code}

    @app.get("/api/test/teacher-or-admin")
    async def teacher_admin_route(current_user: User = Depends(require_role("TEACHER", "ADMIN"))):
        return {"status": "ok", "user": current_user.user_code}

    # Student token
    student_res = await client.post(
        "/api/v1/auth/login",
        json={"user_code_or_email": "SV2026001", "password": "Student@123"},
    )
    student_token = student_res.json()["access_token"]
    student_header = {"Authorization": f"Bearer {student_token}"}

    # Teacher token
    teacher_res = await client.post(
        "/api/v1/auth/login",
        json={"user_code_or_email": "GV001", "password": "Teacher@123"},
    )
    teacher_token = teacher_res.json()["access_token"]
    teacher_header = {"Authorization": f"Bearer {teacher_token}"}

    # Admin token
    admin_res = await client.post(
        "/api/v1/auth/login",
        json={"user_code_or_email": "AD001", "password": "Admin@123"},
    )
    admin_token = admin_res.json()["access_token"]
    admin_header = {"Authorization": f"Bearer {admin_token}"}

    # 1. Student accessing admin-only -> 403 Forbidden
    res = await client.get("/api/test/admin-only", headers=student_header)
    assert res.status_code == 403
    assert "Quyền truy cập bị từ chối" in res.json()["detail"]

    # 2. Teacher accessing admin-only -> 403 Forbidden
    res = await client.get("/api/test/admin-only", headers=teacher_header)
    assert res.status_code == 403

    # 3. Admin accessing admin-only -> 200 OK
    res = await client.get("/api/test/admin-only", headers=admin_header)
    assert res.status_code == 200
    assert res.json()["user"] == "AD001"

    # 4. Teacher accessing teacher-or-admin -> 200 OK
    res = await client.get("/api/test/teacher-or-admin", headers=teacher_header)
    assert res.status_code == 200

    # 5. Student accessing teacher-or-admin -> 403 Forbidden
    res = await client.get("/api/test/teacher-or-admin", headers=student_header)
    assert res.status_code == 403

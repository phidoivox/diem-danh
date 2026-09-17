import json
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from detect_ai.core.config import S
from detect_ai.core.database import Base
from detect_ai.core.deps import get_db
from detect_ai.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from detect_ai.main import app
from detect_ai.models.user import Role, StudentProfile, TeacherProfile, User


@pytest_asyncio.fixture
async def test_session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield session_maker

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_session(test_session_maker):
    async with test_session_maker() as session:
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

        # Seed Student with face embedding
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
            face_embedding="[0.123, -0.456, 0.789, 0.001]",
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

    async with test_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_session_maker):
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


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
async def test_login_student_success_and_no_face_embedding(
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

    # Privacy constraint: Absolutely NO face_embedding in the JSON response
    res_str = json.dumps(data)
    assert "face_embedding" not in res_str
    assert "0.123" not in res_str


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
    assert "face_embedding" not in json.dumps(me_data)


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
    from detect_ai.api.deps_auth import require_role
    from detect_ai.models.user import User

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


# ==========================================
# 5. Tests for Kiosk API Key (verify_kiosk_api_key)
# ==========================================
@pytest.mark.asyncio
async def test_kiosk_api_key_verification(client: AsyncClient):
    from fastapi import Depends
    from detect_ai.api.deps_auth import verify_kiosk_api_key

    @app.post("/api/test/kiosk-ping")
    async def kiosk_ping_route(key: str = Depends(verify_kiosk_api_key)):
        return {"status": "ok", "kiosk": True}

    # Valid Key
    res_valid = await client.post(
        "/api/test/kiosk-ping",
        headers={"X-Kiosk-Api-Key": S.kiosk_api_key},
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["kiosk"] is True

    # Invalid Key
    res_invalid = await client.post(
        "/api/test/kiosk-ping",
        headers={"X-Kiosk-Api-Key": "wrong-secret-key"},
    )
    assert res_invalid.status_code == 401
    assert "Invalid or missing Kiosk API Key" in res_invalid.json()["detail"]

    # Missing Key
    res_missing = await client.post("/api/test/kiosk-ping")
    assert res_missing.status_code == 401
    assert "Invalid or missing Kiosk API Key" in res_missing.json()["detail"]

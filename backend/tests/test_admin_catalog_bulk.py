"""Test courses / administrative-classes / bulk / class-names (fix FE 404)."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from detect_ai.shared.kernel.database import Base
from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.security import create_access_token, get_password_hash
from detect_ai.main import app
from detect_ai.modules.academic.infrastructure.models import Class, ClassStudent
from detect_ai.shared.kernel.system_setting import SystemSetting
from detect_ai.modules.identity.infrastructure.models import Role, StudentProfile, TeacherProfile, User


@pytest_asyncio.fixture
async def test_session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

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
async def seeded_data(test_session_maker):
    async with test_session_maker() as session:
        admin_role = Role(role_name="ADMIN")
        teacher_role = Role(role_name="TEACHER")
        student_role = Role(role_name="STUDENT")
        session.add_all([admin_role, teacher_role, student_role])
        await session.commit()
        admin = User(
            user_code="ADMIN01",
            full_name="System Administrator",
            email="admin@school.edu.vn",
            password_hash=get_password_hash("Admin@123"),
            role_id=admin_role.id,
            is_active=True,
        )
        session.add(admin)
        teacher = User(
            user_code="GV001",
            full_name="ThS. Nguyen Van Giang",
            email="giangnv@school.edu.vn",
            password_hash=get_password_hash("Teacher@123"),
            role_id=teacher_role.id,
            is_active=True,
        )
        session.add(teacher)
        await session.commit()
        await session.refresh(teacher)
        session.add(TeacherProfile(
            user_id=teacher.id, department="Khoa CNTT", academic_title="Thac si", office_room="A1-402"))
        student = User(
            user_code="SV2026001",
            full_name="Le Thi Mai",
            email="mailt@student.edu.vn",
            password_hash=get_password_hash("Student@123"),
            role_id=student_role.id,
            is_active=True,
        )
        session.add(student)
        await session.commit()
        await session.refresh(student)
        session.add(StudentProfile(
            user_id=student.id, total_point=100, class_name="CNTT-K24A", major="Ky thuat phan mem"))
        session.add_all([
            SystemSetting(key="POINT_FULL_ATTENDANCE", value="2"),
            SystemSetting(key="POINT_LATE", value="-1"),
            SystemSetting(key="LATE_TOLERANCE_MINUTES", value="15"),
            SystemSetting(key="REQUIRE_CHECKOUT", value="false"),
        ])
        await session.commit()
        return {"admin_id": admin.id, "teacher_id": teacher.id, "student_id": student.id}


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


def make_auth_header(user_code: str, role: str) -> dict:
    token = create_access_token(data={"sub": user_code, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_courses_crud(client: AsyncClient, seeded_data):
    headers = make_auth_header("ADMIN01", "ADMIN")
    payload = {"course_code": "INT101", "course_name": "Nhap mon CNTT", "credits": 3,
               "default_sessions": 15, "description": "Mon co so"}
    res = await client.post("/api/v1/admin/academic/courses", json=payload, headers=headers)
    assert res.status_code in [200, 201], res.text
    course_id = res.json()["id"]
    dup = await client.post("/api/v1/admin/academic/courses", json=payload, headers=headers)
    assert dup.status_code == 400
    res_list = await client.get("/api/v1/admin/academic/courses?q=INT", headers=headers)
    assert res_list.status_code == 200
    assert any(c["id"] == course_id for c in res_list.json()["items"])
    res_up = await client.put(
        f"/api/v1/admin/academic/courses/{course_id}",
        json={"course_name": "Nhap mon CNTT 2"},
        headers=headers,
    )
    assert res_up.status_code == 200
    assert res_up.json()["course_name"] == "Nhap mon CNTT 2"
    student_headers = make_auth_header("SV2026001", "STUDENT")
    res_forbid = await client.get("/api/v1/admin/academic/courses", headers=student_headers)
    assert res_forbid.status_code == 403
    res_del = await client.delete(f"/api/v1/admin/academic/courses/{course_id}", headers=headers)
    assert res_del.status_code == 200


@pytest.mark.asyncio
async def test_admin_class_uses_course_id(client: AsyncClient, seeded_data):
    headers = make_auth_header("ADMIN01", "ADMIN")
    course = (await client.post("/api/v1/admin/academic/courses",
        json={"course_code": "CS201", "course_name": "Cau truc du lieu"}, headers=headers)).json()
    res = await client.post("/api/v1/admin/academic/classes", json={"class_code": "CS201_01",
        "course_id": course["id"], "teacher_id": seeded_data["teacher_id"],
        "semester": "HK1_2026", "total_sessions": 15}, headers=headers)
    assert res.status_code in [200, 201], res.text
    body = res.json()
    assert body["course_id"] == course["id"]
    assert body["course_code"] == "CS201"
    assert body["course_name"] == "Cau truc du lieu"


@pytest.mark.asyncio
async def test_admin_sh_and_bulk_and_class_names(client: AsyncClient, seeded_data):
    headers = make_auth_header("ADMIN01", "ADMIN")
    teacher_id = seeded_data["teacher_id"]
    student_id = seeded_data["student_id"]
    ac = (await client.post("/api/v1/admin/academic/administrative-classes",
        json={"class_code": "21KTPM01", "academic_year": "2021-2025", "faculty": "CNTT"},
        headers=headers)).json()
    assert ac["class_code"] == "21KTPM01"
    res_list = await client.get("/api/v1/admin/academic/administrative-classes", headers=headers)
    assert res_list.status_code == 200
    assert any(i["class_code"] == "21KTPM01" for i in res_list.json()["items"])
    res_user = await client.put(f"/api/v1/admin/users/{student_id}",
        json={"admin_class_id": ac["id"]}, headers=headers)
    assert res_user.status_code == 200, res_user.text
    assert res_user.json()["student_profile"]["admin_class_id"] == ac["id"]
    assert res_user.json()["student_profile"]["class_name"] == "21KTPM01"
    res_names = await client.get("/api/v1/admin/users/class-names", headers=headers)
    assert res_names.status_code == 200
    assert "21KTPM01" in res_names.json()
    res_class = await client.post("/api/v1/admin/academic/classes",
        json={"class_code": "BULK_01", "course_name": "Mon bulk",
              "teacher_id": teacher_id, "semester": "HK1_2026"}, headers=headers)
    assert res_class.status_code in [200, 201], res_class.text
    class_id = res_class.json()["id"]
    res_bulk = await client.post(f"/api/v1/admin/academic/classes/{class_id}/students/bulk",
        json={"student_ids": [], "class_names": [], "admin_class_ids": [ac["id"]]}, headers=headers)
    assert res_bulk.status_code == 200, res_bulk.text
    assert student_id in res_bulk.json()["enrolled"]
    res_bulk2 = await client.post(f"/api/v1/admin/academic/classes/{class_id}/students/bulk",
        json={"student_ids": [student_id], "class_names": [], "admin_class_ids": [ac["id"]]},
        headers=headers)
    assert student_id in res_bulk2.json()["skipped"]
    sh_id = ac["id"]
    res_sh = await client.get(
        f"/api/v1/admin/academic/administrative-classes/{sh_id}/students", headers=headers)
    assert res_sh.status_code == 200
    assert any(s["id"] == student_id for s in res_sh.json())
import io
from datetime import date, time, datetime, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from detect_ai.shared.kernel.database import Base
from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.security import create_access_token, get_password_hash
from detect_ai.main import app
from detect_ai.modules.academic.infrastructure.models import Class, ClassStudent, Schedule
from detect_ai.modules.attendance.infrastructure.models import Attendance, AttendanceStatus
from detect_ai.modules.evaluation.infrastructure.models import PointLedger
from detect_ai.shared.kernel.system_setting import SystemSetting
from detect_ai.modules.identity.infrastructure.models import Role, StudentProfile, TeacherProfile, User
from detect_ai.modules.recognition.infrastructure.models import FaceEmbedding


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
async def seeded_data(test_session_maker):
    async with test_session_maker() as session:
        # Roles
        admin_role = Role(role_name="ADMIN")
        teacher_role = Role(role_name="TEACHER")
        student_role = Role(role_name="STUDENT")
        session.add_all([admin_role, teacher_role, student_role])
        await session.commit()

        # Admin user
        admin = User(
            user_code="ADMIN01",
            full_name="System Administrator",
            email="admin@school.edu.vn",
            password_hash=get_password_hash("Admin@123"),
            role_id=admin_role.id,
            is_active=True,
        )
        session.add(admin)

        # Teacher user
        teacher = User(
            user_code="GV001",
            full_name="ThS. Nguyễn Văn Giảng",
            email="giangnv@school.edu.vn",
            password_hash=get_password_hash("Teacher@123"),
            role_id=teacher_role.id,
            is_active=True,
        )
        session.add(teacher)
        await session.commit()
        await session.refresh(teacher)

        teacher_profile = TeacherProfile(
            user_id=teacher.id,
            department="Khoa CNTT",
            academic_title="Thạc sĩ",
            office_room="A1-402",
        )
        session.add(teacher_profile)

        # Student user
        student = User(
            user_code="SV2026001",
            full_name="Lê Thị Mai",
            email="mailt@student.edu.vn",
            password_hash=get_password_hash("Student@123"),
            role_id=student_role.id,
            is_active=True,
        )
        session.add(student)
        await session.commit()
        await session.refresh(student)

        student_profile = StudentProfile(
            user_id=student.id,
            total_point=100,
            class_name="CNTT-K24A",
            major="Kỹ thuật phần mềm",
        )
        session.add(student_profile)

        # System Settings
        settings = [
            SystemSetting(key="POINT_FULL_ATTENDANCE", value="2", description="Điểm chuyên cần"),
            SystemSetting(key="POINT_LATE", value="-1", description="Trừ trễ"),
            SystemSetting(key="LATE_TOLERANCE_MINUTES", value="15", description="Phút trễ"),
            SystemSetting(key="REQUIRE_CHECKOUT", value="false", description="Yêu cầu checkout"),
        ]
        session.add_all(settings)
        await session.commit()

        return {
            "admin_id": admin.id,
            "teacher_id": teacher.id,
            "student_id": student.id,
        }


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


# =====================================================================
# 1. RBAC PERMISSIONS TESTS
# =====================================================================
@pytest.mark.asyncio
async def test_admin_routes_require_admin_role(client: AsyncClient, seeded_data):
    """Test that STUDENT and TEACHER tokens cannot access admin routes."""
    admin_headers = make_auth_header("ADMIN01", "ADMIN")
    teacher_headers = make_auth_header("GV001", "TEACHER")
    student_headers = make_auth_header("SV2026001", "STUDENT")

    test_urls = [
        "/api/v1/admin/users",
        "/api/v1/admin/academic/classes",
        "/api/v1/admin/academic/schedules",
        "/api/v1/admin/settings",
    ]

    for url in test_urls:
        # Unauthenticated -> 401
        res_no_auth = await client.get(url)
        assert res_no_auth.status_code == 401, f"{url} should require auth"

        # Student -> 403
        res_student = await client.get(url, headers=student_headers)
        assert res_student.status_code == 403, f"{url} should forbid student"

        # Teacher -> 403
        res_teacher = await client.get(url, headers=teacher_headers)
        assert res_teacher.status_code == 403, f"{url} should forbid teacher"

        # Admin -> 200
        res_admin = await client.get(url, headers=admin_headers)
        assert res_admin.status_code == 200, f"{url} should allow admin: {res_admin.text}"


# =====================================================================
# 2. USER CRUD TESTS
# =====================================================================
@pytest.mark.asyncio
async def test_admin_create_student_user(client: AsyncClient, seeded_data):
    """Admin creates a new student user and its profile."""
    headers = make_auth_header("ADMIN01", "ADMIN")
    payload = {
        "user_code": "SV2026999",
        "full_name": "Phạm Văn Tân",
        "email": "tanpv@student.edu.vn",
        "password": "Password@123",
        "role_name": "STUDENT",
        "class_name": "CNTT-K24B",
        "major": "An toàn thông tin",
    }

    res = await client.post("/api/v1/admin/users", json=payload, headers=headers)
    assert res.status_code in [200, 201], res.text
    data = res.json()
    assert data["user_code"] == "SV2026999"
    assert data["role"] == "STUDENT"
    assert "student_profile" in data and data["student_profile"] is not None
    assert data["student_profile"]["class_name"] == "CNTT-K24B"
    assert data["student_profile"]["major"] == "An toàn thông tin"
    assert "face_embedding" not in data.get("student_profile", {})
    # Điểm khởi đầu SV thường = 95.
    assert data["student_profile"]["total_point"] == 95


@pytest.mark.asyncio
async def test_admin_create_teacher_user(client: AsyncClient, seeded_data):
    """Admin creates a new teacher user and its profile."""
    headers = make_auth_header("ADMIN01", "ADMIN")
    payload = {
        "user_code": "GV002",
        "full_name": "PGS.TS. Hoàng Kim",
        "email": "kimhk@school.edu.vn",
        "password": "Password@123",
        "role_name": "TEACHER",
        "department": "Khoa Điện Tử",
        "academic_title": "Phó Giáo Sư",
        "office_room": "B2-301",
    }

    res = await client.post("/api/v1/admin/users", json=payload, headers=headers)
    assert res.status_code in [200, 201], res.text
    data = res.json()
    assert data["user_code"] == "GV002"
    assert data["role"] == "TEACHER"
    assert "teacher_profile" in data and data["teacher_profile"] is not None
    assert data["teacher_profile"]["department"] == "Khoa Điện Tử"
    assert data["teacher_profile"]["office_room"] == "B2-301"


@pytest.mark.asyncio
async def test_admin_list_users_filters_and_pagination(client: AsyncClient, seeded_data):
    """Admin lists users with search, role filter, and ensures no face_embedding is returned."""
    headers = make_auth_header("ADMIN01", "ADMIN")

    # List all
    res = await client.get("/api/v1/admin/users", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert body["total"] >= 3
    # Verify no face_embedding is leaked
    for item in body["items"]:
        assert "face_embedding" not in item
        if item.get("student_profile"):
            assert "face_embedding" not in item["student_profile"]

    # Filter by role
    res_student = await client.get("/api/v1/admin/users?role=STUDENT", headers=headers)
    assert res_student.status_code == 200
    for item in res_student.json()["items"]:
        assert item["role"] == "STUDENT"

    # Search by q
    res_search = await client.get("/api/v1/admin/users?q=Gi%E1%BA%A3ng", headers=headers)
    assert res_search.status_code == 200
    assert any("Giảng" in item["full_name"] for item in res_search.json()["items"])


@pytest.mark.asyncio
async def test_admin_update_user(client: AsyncClient, seeded_data):
    """Admin updates user info and profile."""
    headers = make_auth_header("ADMIN01", "ADMIN")
    teacher_id = seeded_data["teacher_id"]

    update_payload = {
        "full_name": "GS.TS. Nguyễn Văn Giảng",
        "department": "Viện Trí Tuệ Nhân Tạo",
        "academic_title": "Giáo Sư",
    }
    res = await client.put(f"/api/v1/admin/users/{teacher_id}", json=update_payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["full_name"] == "GS.TS. Nguyễn Văn Giảng"
    assert data["teacher_profile"]["academic_title"] == "Giáo Sư"
    assert data["teacher_profile"]["department"] == "Viện Trí Tuệ Nhân Tạo"


@pytest.mark.asyncio
async def test_admin_soft_delete_preserves_historical_records(
    client: AsyncClient, seeded_data, test_session_maker
):
    """Soft delete sets deleted_at, hides from active queries, but retains relational integrity."""
    headers = make_auth_header("ADMIN01", "ADMIN")
    student_id = seeded_data["student_id"]

    # Create dummy schedule and attendance record for student
    async with test_session_maker() as session:
        clazz = Class(
            class_code="CS_TEST_SOFT",
            course_name="Test Class",
            teacher_id=seeded_data["teacher_id"],
            semester="HK1",
        )
        session.add(clazz)
        await session.commit()
        await session.refresh(clazz)

        sched = Schedule(
            class_id=clazz.id,
            room_name="P.999",
            study_date=date(2026, 9, 20),
            start_time=time(7, 0),
            end_time=time(9, 0),
            session_order=1,
        )
        session.add(sched)
        await session.commit()
        await session.refresh(sched)

        att = Attendance(
            schedule_id=sched.id,
            student_id=student_id,
            status=AttendanceStatus.PRESENT,
        )
        ledger = PointLedger(
            student_id=student_id,
            schedule_id=sched.id,
            point_delta=2,
            reason_code="ATTENDANCE",
            description="Test attendance points",
        )
        session.add_all([att, ledger])
        await session.commit()

    # Soft delete the student
    res_del = await client.delete(f"/api/v1/admin/users/{student_id}", headers=headers)
    assert res_del.status_code == 200, res_del.text

    # Student should no longer appear in GET /users
    res_list = await client.get("/api/v1/admin/users", headers=headers)
    user_ids = [u["id"] for u in res_list.json()["items"]]
    assert student_id not in user_ids

    # Student cannot log in anymore
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"user_code_or_email": "SV2026001", "password": "Student@123"},
    )
    assert login_res.status_code == 401

    # Historical attendance & ledger records still exist in DB
    async with test_session_maker() as session:
        user_in_db = (
            await session.execute(select(User).where(User.id == student_id))
        ).scalar_one()
        assert user_in_db.deleted_at is not None

        att_in_db = (
            await session.execute(
                select(Attendance).where(Attendance.student_id == student_id)
            )
        ).scalar_one()
        assert att_in_db.status == AttendanceStatus.PRESENT

        ledger_in_db = (
            await session.execute(
                select(PointLedger).where(PointLedger.student_id == student_id)
            )
        ).scalar_one()
        assert ledger_in_db.point_delta == 2


@pytest.mark.asyncio
async def test_admin_face_enroll(client: AsyncClient, seeded_data, test_session_maker):
    """Admin uploads portrait image to enroll face vector."""
    headers = make_auth_header("ADMIN01", "ADMIN")
    student_id = seeded_data["student_id"]

    # Create dummy 100x100 RGB image
    import cv2
    import numpy as np

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".jpg", img)
    img_bytes = encoded.tobytes()

    # Mock enroll_image ở biên recognition để không cần model thật
    from unittest.mock import patch

    async def _fake_enroll(db, user_id, img_bgr, source="avatar", engine=None, on_enrolled=None):
        from detect_ai.modules.recognition.infrastructure.face_engine import embedding_to_json

        row = FaceEmbedding(
            user_id=user_id,
            embedding=embedding_to_json(np.full((512,), 0.05, dtype=np.float32)),
            quality=0.9,
            source=source,
            is_active=True,
        )
        db.add(row)
        await db.commit()
        return row

    with patch(
        "detect_ai.modules.recognition.public.enroll_image",
        side_effect=_fake_enroll,
    ):
        res = await client.post(
            f"/api/v1/admin/users/{student_id}/face-enroll",
            files={"photo": ("face.jpg", io.BytesIO(img_bytes), "image/jpeg")},
            headers=headers,
        )
        assert res.status_code == 200, res.text
        assert res.json()["face_enrolled"] is True

    # Verify face_embeddings có row mới
    async with test_session_maker() as session:
        rows = (
            await session.execute(
                select(FaceEmbedding).where(FaceEmbedding.user_id == student_id)
            )
        ).scalars().all()
        assert len(rows) >= 1
        assert "0.05" in rows[-1].embedding


# =====================================================================
# 3. CLASSES & ENROLLMENT CRUD TESTS
# =====================================================================
@pytest.mark.asyncio
async def test_admin_class_crud_and_enrollment(client: AsyncClient, seeded_data):
    """Admin creates a class, enrolls a student, prevents duplicate, and lists enrolled students."""
    headers = make_auth_header("ADMIN01", "ADMIN")
    teacher_id = seeded_data["teacher_id"]
    student_id = seeded_data["student_id"]

    # 1. Create class
    class_payload = {
        "class_code": "AI_ENG_101",
        "course_name": "Trí tuệ Nhân tạo Ứng dụng",
        "teacher_id": teacher_id,
        "semester": "HK1_2026",
        "total_sessions": 15,
    }
    res_create = await client.post(
        "/api/v1/admin/academic/classes", json=class_payload, headers=headers
    )
    assert res_create.status_code in [200, 201], res_create.text
    created_class = res_create.json()
    class_id = created_class["id"]
    assert created_class["class_code"] == "AI_ENG_101"

    # 2. List classes
    res_list = await client.get("/api/v1/admin/academic/classes", headers=headers)
    assert res_list.status_code == 200
    classes = res_list.json()["items"]
    target_class = next(c for c in classes if c["id"] == class_id)
    assert "ThS. Nguyễn Văn Giảng" in target_class["teacher_name"]
    assert target_class["student_count"] == 0

    # 3. Enroll student into class
    res_enroll = await client.post(
        f"/api/v1/admin/academic/classes/{class_id}/students",
        json={"student_id": student_id},
        headers=headers,
    )
    assert res_enroll.status_code in [200, 201], res_enroll.text
    assert res_enroll.json()["ok"] is True

    # 4. Duplicate enrollment must be rejected with 400
    res_dup = await client.post(
        f"/api/v1/admin/academic/classes/{class_id}/students",
        json={"student_id": student_id},
        headers=headers,
    )
    assert res_dup.status_code == 400
    assert "đã có trong lớp" in res_dup.text or "duplicate" in res_dup.text.lower()

    # 5. List students in class
    res_students = await client.get(
        f"/api/v1/admin/academic/classes/{class_id}/students", headers=headers
    )
    assert res_students.status_code == 200
    students = res_students.json()
    assert len(students) == 1
    assert students[0]["id"] == student_id
    assert "face_embedding" not in students[0]

    # Verify student_count is now 1
    res_list2 = await client.get("/api/v1/admin/academic/classes", headers=headers)
    target_class2 = next(c for c in res_list2.json()["items"] if c["id"] == class_id)
    assert target_class2["student_count"] == 1

    # 6. Remove student from class
    res_remove = await client.delete(
        f"/api/v1/admin/academic/classes/{class_id}/students/{student_id}",
        headers=headers,
    )
    assert res_remove.status_code == 200
    assert res_remove.json()["ok"] is True

    # Verify student list is empty now
    res_students_empty = await client.get(
        f"/api/v1/admin/academic/classes/{class_id}/students", headers=headers
    )
    assert len(res_students_empty.json()) == 0


# =====================================================================
# 4. SCHEDULES & ROOM CONFLICT CONSTRAINT TESTS
# =====================================================================
@pytest.mark.asyncio
async def test_admin_schedule_room_conflict_constraint(client: AsyncClient, seeded_data):
    """Test anti-room-collision logic:
    Schedule A (08:00 - 10:00 at P.101) -> 200
    Invalid time (10:00 - 08:00) -> 422
    Schedule B (09:00 - 11:00 at P.101) -> 400 (Overlap conflict)
    Schedule C (10:00 - 12:00 at P.101) -> 200 (Adjacent, no conflict)
    """
    headers = make_auth_header("ADMIN01", "ADMIN")

    # Setup class first
    class_payload = {
        "class_code": "CS_SCHEDULE_TEST",
        "course_name": "Schedule Test",
        "teacher_id": seeded_data["teacher_id"],
        "semester": "HK1_2026",
    }
    class_res = await client.post(
        "/api/v1/admin/academic/classes", json=class_payload, headers=headers
    )
    class_id = class_res.json()["id"]

    # 1. Invalid time: start_time >= end_time -> 422
    bad_time_sched = {
        "class_id": class_id,
        "room_name": "P.101",
        "study_date": "2026-09-25",
        "start_time": "10:00:00",
        "end_time": "08:00:00",
        "session_order": 1,
    }
    res_bad = await client.post(
        "/api/v1/admin/academic/schedules", json=bad_time_sched, headers=headers
    )
    assert res_bad.status_code == 422, res_bad.text
    assert "start_time phải nhỏ hơn end_time" in res_bad.text

    # 2. Schedule A: 08:00 - 10:00 at P.101 -> 200 OK
    sched_a = {
        "class_id": class_id,
        "room_name": "P.101",
        "study_date": "2026-09-25",
        "start_time": "08:00:00",
        "end_time": "10:00:00",
        "session_order": 1,
    }
    res_a = await client.post(
        "/api/v1/admin/academic/schedules", json=sched_a, headers=headers
    )
    assert res_a.status_code in [200, 201], res_a.text

    # 3. Schedule B: 09:00 - 11:00 at P.101 -> 400 Bad Request (Overlap conflict)
    sched_b = {
        "class_id": class_id,
        "room_name": "P.101",
        "study_date": "2026-09-25",
        "start_time": "09:00:00",
        "end_time": "11:00:00",
        "session_order": 2,
    }
    res_b = await client.post(
        "/api/v1/admin/academic/schedules", json=sched_b, headers=headers
    )
    assert res_b.status_code == 400, f"Expected 400 but got {res_b.status_code}: {res_b.text}"
    assert "Phòng học P.101 đã có lịch học trong khung giờ này" in res_b.text

    # 4. Schedule C: 10:00 - 12:00 at P.101 -> 200 OK (Adjacent boundary, start == previous end)
    sched_c = {
        "class_id": class_id,
        "room_name": "P.101",
        "study_date": "2026-09-25",
        "start_time": "10:00:00",
        "end_time": "12:00:00",
        "session_order": 2,
    }
    res_c = await client.post(
        "/api/v1/admin/academic/schedules", json=sched_c, headers=headers
    )
    assert res_c.status_code in [200, 201], res_c.text

    # 5. Query schedules by room_name & study_date
    res_get = await client.get(
        "/api/v1/admin/academic/schedules?room_name=P.101&study_date=2026-09-25",
        headers=headers,
    )
    assert res_get.status_code == 200
    schedules = res_get.json()
    assert len(schedules) == 2  # Sched A and Sched C


# =====================================================================
# 5. SYSTEM SETTINGS CRUD TESTS
# =====================================================================
@pytest.mark.asyncio
async def test_admin_settings_get_and_put(client: AsyncClient, seeded_data):
    """Admin reads and updates system configuration settings."""
    headers = make_auth_header("ADMIN01", "ADMIN")

    # 1. GET settings
    res = await client.get("/api/v1/admin/settings", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert "settings" in body
    assert body["settings"]["POINT_FULL_ATTENDANCE"] == "2"
    assert body["settings"]["LATE_TOLERANCE_MINUTES"] == "15"

    # 2. PUT settings update
    update_payload = {
        "POINT_FULL_ATTENDANCE": "5",
        "LATE_TOLERANCE_MINUTES": "20",
        "REQUIRE_CHECKOUT": "true",
        "MAX_ABSENCE_PERCENT_EXAM_BAN": "25",
    }
    res_update = await client.put(
        "/api/v1/admin/settings", json=update_payload, headers=headers
    )
    assert res_update.status_code == 200, res_update.text
    updated_body = res_update.json()
    assert updated_body["settings"]["POINT_FULL_ATTENDANCE"] == "5"
    assert updated_body["settings"]["LATE_TOLERANCE_MINUTES"] == "20"
    assert updated_body["settings"]["REQUIRE_CHECKOUT"] == "true"
    assert updated_body["settings"]["MAX_ABSENCE_PERCENT_EXAM_BAN"] == "25"

    # 3. GET settings again to verify persistent storage
    res_check = await client.get("/api/v1/admin/settings", headers=headers)
    assert res_check.status_code == 200
    assert res_check.json()["settings"]["POINT_FULL_ATTENDANCE"] == "5"

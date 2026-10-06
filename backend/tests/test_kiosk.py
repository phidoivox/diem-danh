import json
from datetime import date, time, datetime, timezone
import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from detect_ai.shared.kernel.config import S
from detect_ai.shared.kernel.database import Base
from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.security import get_password_hash
from detect_ai.main import app
from detect_ai.modules.academic.infrastructure.models import Class, ClassStudent, Schedule
from detect_ai.modules.attendance.infrastructure.models import Attendance, AttendanceStatus
from detect_ai.shared.kernel.system_setting import SystemSetting
from detect_ai.modules.identity.infrastructure.models import Role, StudentProfile, User
from detect_ai.modules.recognition.infrastructure.models import FaceEmbedding
from detect_ai.streamers import face_store


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
async def kiosk_test_data(test_session_maker):
    async with test_session_maker() as session:
        # 1. Roles
        admin_role = Role(role_name="ADMIN")
        teacher_role = Role(role_name="TEACHER")
        student_role = Role(role_name="STUDENT")
        session.add_all([admin_role, teacher_role, student_role])
        await session.commit()

        # 2. Teacher
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

        # 3. Students
        # Student 1: Enrolled in Class 1 with valid 512-dim embedding
        dummy_vec1 = np.ones(512, dtype=np.float32) * 0.05
        student1 = User(
            user_code="SV001",
            full_name="Nguyễn Văn A",
            email="sv001@school.edu.vn",
            password_hash=get_password_hash("123456"),
            role_id=student_role.id,
            is_active=True,
        )
        session.add(student1)
        await session.commit()
        await session.refresh(student1)

        sp1 = StudentProfile(
            user_id=student1.id,
            class_name="CNTT-K22A",
            total_point=100,
        )
        session.add(sp1)
        session.add(FaceEmbedding(
            user_id=student1.id,
            embedding=json.dumps(dummy_vec1.tolist()),
            quality=0.9,
            source="avatar",
            is_active=True,
        ))

        # Student 2: Not enrolled in Class 1 (different class)
        student2 = User(
            user_code="SV002",
            full_name="Trần Thị B",
            email="sv002@school.edu.vn",
            password_hash=get_password_hash("123456"),
            role_id=student_role.id,
            is_active=True,
        )
        session.add(student2)
        await session.commit()
        await session.refresh(student2)

        sp2 = StudentProfile(
            user_id=student2.id,
            class_name="CNTT-K22B",
            total_point=100,
        )
        session.add(sp2)
        session.add(FaceEmbedding(
            user_id=student2.id,
            embedding=json.dumps([0.1, 0.2, 0.3]),  # short embedding to test padding
            quality=0.5,
            source="avatar",
            is_active=True,
        ))

        # Student 3: Inactive student
        student3 = User(
            user_code="SV003",
            full_name="Lê Văn Inactive",
            email="sv003@school.edu.vn",
            password_hash=get_password_hash("123456"),
            role_id=student_role.id,
            is_active=False,
        )
        session.add(student3)
        await session.commit()
        await session.refresh(student3)

        sp3 = StudentProfile(
            user_id=student3.id,
            class_name="CNTT-K22A",
            total_point=100,
        )
        session.add(sp3)
        session.add(FaceEmbedding(
            user_id=student3.id,
            embedding=json.dumps([0.5] * 512),
            quality=0.9,
            source="avatar",
            is_active=True,
        ))

        # Student 4: Soft-deleted student
        student4 = User(
            user_code="SV004",
            full_name="Phạm Văn Deleted",
            email="sv004@school.edu.vn",
            password_hash=get_password_hash("123456"),
            role_id=student_role.id,
            is_active=True,
            deleted_at=datetime.now(timezone.utc),
        )
        session.add(student4)
        await session.commit()
        await session.refresh(student4)

        sp4 = StudentProfile(
            user_id=student4.id,
            class_name="CNTT-K22A",
            total_point=100,
        )
        session.add(sp4)
        session.add(FaceEmbedding(
            user_id=student4.id,
            embedding=json.dumps([0.6] * 512),
            quality=0.9,
            source="avatar",
            is_active=True,
        ))

        # 4. Class
        clazz = Class(
            class_code="INT3306_01",
            course_name="Phát triển Ứng dụng AI",
            teacher_id=teacher.id,
            semester="2025-2026.1",
            total_sessions=15,
        )
        session.add(clazz)
        await session.commit()
        await session.refresh(clazz)

        # Enroll student 1 into Class 1
        cs1 = ClassStudent(class_id=clazz.id, student_id=student1.id)
        session.add(cs1)

        # 5. Schedule: Today, Room A1-301, 08:00 - 10:00
        today = date.today()
        schedule = Schedule(
            class_id=clazz.id,
            room_name="A1-301",
            study_date=today,
            start_time=time(8, 0),
            end_time=time(10, 0),
            session_order=1,
        )
        session.add(schedule)

        # 6. System settings
        session.add_all([
            SystemSetting(key="LATE_TOLERANCE_MINUTES", value="15", description="Phút trễ"),
            SystemSetting(key="POINT_FULL_ATTENDANCE", value="10", description="Điểm đúng giờ"),
        ])

        await session.commit()

        return {
            "teacher": teacher,
            "student1": student1,
            "student2": student2,
            "student3": student3,
            "student4": student4,
            "clazz": clazz,
            "schedule": schedule,
            "today": today,
        }


@pytest.mark.asyncio
async def test_face_store_decode_and_reload(test_session_maker, kiosk_test_data):
    # Test decode_embedding directly
    vec_json = face_store.decode_embedding("[0.1, 0.2, 0.3]")
    assert vec_json is not None
    assert vec_json.shape == (512,)
    assert np.isclose(vec_json[0], 0.1)

    # Test bytes decoding
    raw_bytes = np.ones(512, dtype=np.float32).tobytes()
    vec_bytes = face_store.decode_embedding(raw_bytes)
    assert vec_bytes is not None
    assert vec_bytes.shape == (512,)

    # Test invalid embedding
    assert face_store.decode_embedding(None) is None
    assert face_store.decode_embedding("") is None
    assert face_store.decode_embedding("invalid_string") is None

    # Test reload with active/inactive/deleted filtering
    async with test_session_maker() as s:
        await face_store.reload(s)

    codes = [m["code"] for m in face_store.meta]
    assert "SV001" in codes
    assert "SV002" in codes
    assert "SV003" not in codes  # inactive
    assert "SV004" not in codes  # deleted
    assert len(face_store.embs) == len(face_store.meta)


@pytest.mark.asyncio
async def test_kiosk_api_key_auth(test_session_maker, kiosk_test_data):
    async def override_get_db():
        async with test_session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            today = kiosk_test_data["today"]
            payload = {
                "room_name": "A1-301",
                "student_code": "SV001",
                "has_uniform": True,
                "timestamp": datetime.combine(today, time(8, 5)).isoformat(),
            }

            # 1. Missing header
            res1 = await ac.post("/api/v1/attendance/kiosk-record", json=payload)
            assert res1.status_code == 401

            # 2. Invalid header
            res2 = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json=payload,
                headers={"X-Kiosk-Api-Key": "wrong-key"},
            )
            assert res2.status_code == 401

            # 3. Valid header
            res3 = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json=payload,
                headers={"X-Kiosk-Api-Key": S.kiosk_api_key},
            )
            assert res3.status_code == 200
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_kiosk_check_in_and_check_out_flow(test_session_maker, kiosk_test_data):
    async def override_get_db():
        async with test_session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            headers = {"X-Kiosk-Api-Key": S.kiosk_api_key}
            today = kiosk_test_data["today"]

            # 1. Check-in on time (08:05 <= 08:00 + 15m)
            check_in_time = datetime.combine(today, time(8, 5))
            res_in = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json={
                    "room_name": "A1-301",
                    "student_code": "SV001",
                    "has_uniform": True,
                    "timestamp": check_in_time.isoformat(),
                },
                headers=headers,
            )
            assert res_in.status_code == 200
            data_in = res_in.json()
            assert data_in["type"] == "CHECK_IN"
            assert data_in["student_code"] == "SV001"
            assert data_in["status"] == AttendanceStatus.PRESENT.value
            assert data_in["has_uniform"] is True
            assert data_in["room_name"] == "A1-301"
            assert data_in["class_code"] == "INT3306_01"

            # 2. Check-out at end of class (09:55) with uniform violation
            check_out_time = datetime.combine(today, time(9, 55))
            res_out = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json={
                    "room_name": "A1-301",
                    "student_code": "SV001",
                    "has_uniform": False,  # Violated uniform on checkout
                    "timestamp": check_out_time.isoformat(),
                },
                headers=headers,
            )
            assert res_out.status_code == 200
            data_out = res_out.json()
            assert data_out["type"] == "CHECK_OUT"
            assert data_out["student_code"] == "SV001"
            assert data_out["check_in_time"] is not None
            assert data_out["check_out_time"] is not None
            assert data_out["has_uniform"] is False  # True and False -> False

            # Verify in DB
            async with test_session_maker() as s:
                sched = kiosk_test_data["schedule"]
                stu1 = kiosk_test_data["student1"]
                att = (await s.execute(
                    select(Attendance).where(
                        Attendance.schedule_id == sched.id,
                        Attendance.student_id == stu1.id,
                    )
                )).scalar_one()

                assert att.status == AttendanceStatus.PRESENT
                assert att.has_uniform is False
                assert att.check_in_time is not None
                assert att.check_out_time is not None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_kiosk_check_in_late(test_session_maker, kiosk_test_data):
    async def override_get_db():
        async with test_session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            headers = {"X-Kiosk-Api-Key": S.kiosk_api_key}
            today = kiosk_test_data["today"]

            # Check-in late (08:20 > 08:00 + 15m)
            late_time = datetime.combine(today, time(8, 20))
            res = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json={
                    "room_name": "A1-301",
                    "student_code": "SV001",
                    "has_uniform": True,
                    "timestamp": late_time.isoformat(),
                },
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["type"] == "CHECK_IN"
            assert data["status"] == AttendanceStatus.LATE.value
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_kiosk_buffer_time_and_out_of_schedule(test_session_maker, kiosk_test_data):
    async def override_get_db():
        async with test_session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            headers = {"X-Kiosk-Api-Key": S.kiosk_api_key}
            today = kiosk_test_data["today"]

            # 1. 31 minutes before class (07:29) -> outside buffer -> 404
            res_too_early = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json={
                    "room_name": "A1-301",
                    "student_code": "SV001",
                    "has_uniform": True,
                    "timestamp": datetime.combine(today, time(7, 29)).isoformat(),
                },
                headers=headers,
            )
            assert res_too_early.status_code == 404

            # 2. Exactly 30 minutes before class (07:30) -> within buffer -> 200
            res_valid_early = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json={
                    "room_name": "A1-301",
                    "student_code": "SV001",
                    "has_uniform": True,
                    "timestamp": datetime.combine(today, time(7, 30)).isoformat(),
                },
                headers=headers,
            )
            assert res_valid_early.status_code == 200
            assert res_valid_early.json()["type"] == "CHECK_IN"

            # 3. Exactly 30 minutes after class end (10:30) -> within buffer -> 200 (Check-out)
            res_valid_late = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json={
                    "room_name": "A1-301",
                    "student_code": "SV001",
                    "has_uniform": True,
                    "timestamp": datetime.combine(today, time(10, 30)).isoformat(),
                },
                headers=headers,
            )
            assert res_valid_late.status_code == 200
            assert res_valid_late.json()["type"] == "CHECK_OUT"

            # 4. 31 minutes after class end (10:31) -> outside buffer -> 404
            res_too_late = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json={
                    "room_name": "A1-301",
                    "student_code": "SV001",
                    "has_uniform": True,
                    "timestamp": datetime.combine(today, time(10, 31)).isoformat(),
                },
                headers=headers,
            )
            assert res_too_late.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_kiosk_student_not_enrolled_and_not_found(test_session_maker, kiosk_test_data):
    async def override_get_db():
        async with test_session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            headers = {"X-Kiosk-Api-Key": S.kiosk_api_key}
            today = kiosk_test_data["today"]
            scan_time = datetime.combine(today, time(8, 10)).isoformat()

            # 1. Student not enrolled in class -> 400
            res_not_enrolled = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json={
                    "room_name": "A1-301",
                    "student_code": "SV002",  # Not enrolled
                    "has_uniform": True,
                    "timestamp": scan_time,
                },
                headers=headers,
            )
            assert res_not_enrolled.status_code == 400
            assert "danh sách lớp" in res_not_enrolled.json()["detail"]

            # 2. Non-existent student -> 404
            res_non_existent = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json={
                    "room_name": "A1-301",
                    "student_code": "SV999",
                    "has_uniform": True,
                    "timestamp": scan_time,
                },
                headers=headers,
            )
            assert res_non_existent.status_code == 404

            # 3. Inactive student -> 404
            res_inactive = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json={
                    "room_name": "A1-301",
                    "student_code": "SV003",
                    "has_uniform": True,
                    "timestamp": scan_time,
                },
                headers=headers,
            )
            assert res_inactive.status_code == 404

            # 4. Deleted student -> 404
            res_deleted = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json={
                    "room_name": "A1-301",
                    "student_code": "SV004",
                    "has_uniform": True,
                    "timestamp": scan_time,
                },
                headers=headers,
            )
            assert res_deleted.status_code == 404

            # 5. Wrong room with no schedules -> 404
            res_wrong_room = await ac.post(
                "/api/v1/attendance/kiosk-record",
                json={
                    "room_name": "B2-999",
                    "student_code": "SV001",
                    "has_uniform": True,
                    "timestamp": scan_time,
                },
                headers=headers,
            )
            assert res_wrong_room.status_code == 404
    finally:
        app.dependency_overrides.clear()

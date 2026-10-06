from datetime import date, datetime, time, timedelta, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from detect_ai.shared.kernel.database import Base
from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.security import create_access_token, get_password_hash
from detect_ai.main import app
from detect_ai.modules.academic.infrastructure.models import Class, ClassStudent, Schedule
from detect_ai.modules.attendance.infrastructure.models import Attendance, AttendanceStatus
from detect_ai.modules.evaluation.infrastructure.models import PointLedger
from detect_ai.modules.identity.infrastructure.models import Role, StudentProfile, TeacherProfile, User


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
async def seeded_portal_data(test_session_maker):
    async with test_session_maker() as session:
        # Roles
        admin_role = Role(role_name="ADMIN")
        teacher_role = Role(role_name="TEACHER")
        student_role = Role(role_name="STUDENT")
        session.add_all([admin_role, teacher_role, student_role])
        await session.commit()

        # Users
        admin_user = User(
            user_code="ADMIN01",
            full_name="Quản Trị Viên",
            email="admin@school.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=admin_role.id,
            is_active=True,
        )
        teacher_user = User(
            user_code="GV001",
            full_name="Nguyễn Văn Giảng",
            email="gv@school.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=teacher_role.id,
            is_active=True,
        )
        student1 = User(
            user_code="SV001",
            full_name="Nguyễn Văn An",
            email="an@student.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=student_role.id,
            is_active=True,
        )
        student2 = User(
            user_code="SV002",
            full_name="Trần Thị Bình",
            email="binh@student.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=student_role.id,
            is_active=True,
        )
        session.add_all([admin_user, teacher_user, student1, student2])
        await session.commit()
        await session.refresh(admin_user)
        await session.refresh(teacher_user)
        await session.refresh(student1)
        await session.refresh(student2)

        # Profiles
        sp1 = StudentProfile(user_id=student1.id, class_name="D20CNTT1", major="CNTT", total_point=95)
        sp2 = StudentProfile(user_id=student2.id, class_name="D20CNTT1", major="CNTT", total_point=100)
        tp = TeacherProfile(user_id=teacher_user.id, department="CNTT", academic_title="ThS", office_room="A101")
        session.add_all([sp1, sp2, tp])

        # Classes
        c1 = Class(
            class_code="CS101",
            course_name="Lập trình Python",
            teacher_id=teacher_user.id,
            semester="2026.1",
            total_sessions=15,
        )
        c2 = Class(
            class_code="CS102",
            course_name="Cơ sở dữ liệu",
            teacher_id=teacher_user.id,
            semester="2026.1",
            total_sessions=15,
        )
        session.add_all([c1, c2])
        await session.commit()
        await session.refresh(c1)
        await session.refresh(c2)

        # Enrollments: Student 1 enrolls in CS101 and CS102, Student 2 only in CS102
        cs1 = ClassStudent(class_id=c1.id, student_id=student1.id)
        cs2 = ClassStudent(class_id=c2.id, student_id=student1.id)
        cs3 = ClassStudent(class_id=c2.id, student_id=student2.id)
        session.add_all([cs1, cs2, cs3])
        await session.commit()

        # Schedules
        today = date.today()
        sched1 = Schedule(
            class_id=c1.id,
            room_name="P.301",
            study_date=today,
            start_time=time(7, 30),
            end_time=time(9, 30),
            session_order=1,
        )
        sched2 = Schedule(
            class_id=c1.id,
            room_name="P.301",
            study_date=today + timedelta(days=7),
            start_time=time(7, 30),
            end_time=time(9, 30),
            session_order=2,
        )
        sched3 = Schedule(
            class_id=c2.id,
            room_name="P.402",
            study_date=today + timedelta(days=1),
            start_time=time(13, 0),
            end_time=time(15, 0),
            session_order=1,
        )
        session.add_all([sched1, sched2, sched3])
        await session.commit()
        await session.refresh(sched1)
        await session.refresh(sched2)
        await session.refresh(sched3)

        # Attendance records for student 1
        att1 = Attendance(
            schedule_id=sched1.id,
            student_id=student1.id,
            check_in_time=datetime.now(timezone.utc),
            check_out_time=datetime.now(timezone.utc) + timedelta(hours=2),
            has_uniform=True,
            status=AttendanceStatus.PRESENT,
            note="Đi học đúng giờ",
        )
        session.add(att1)

        # Point ledger for student 1
        pl1 = PointLedger(
            student_id=student1.id,
            schedule_id=sched1.id,
            point_delta=2,
            reason_code="ATTENDANCE_FULL",
            description="Cộng 2 điểm chuyên cần",
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        pl2 = PointLedger(
            student_id=student1.id,
            schedule_id=sched1.id,
            point_delta=-7,
            reason_code="VIOLATION",
            description="Trừ điểm vi phạm nội quy",
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([pl1, pl2])
        await session.commit()

        yield {
            "admin": admin_user,
            "teacher": teacher_user,
            "student1": student1,
            "student2": student2,
            "class1": c1,
            "class2": c2,
            "sched1": sched1,
            "sched2": sched2,
            "sched3": sched3,
        }


@pytest.fixture
def auth_tokens(seeded_portal_data):
    def make_token(user):
        return create_access_token({"sub": str(user.id), "role": user.role.role_name})

    return {
        "admin": make_token(seeded_portal_data["admin"]),
        "teacher": make_token(seeded_portal_data["teacher"]),
        "student1": make_token(seeded_portal_data["student1"]),
        "student2": make_token(seeded_portal_data["student2"]),
    }


@pytest.mark.asyncio
async def test_student_get_schedule(test_session_maker, seeded_portal_data, auth_tokens):
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Student 1 gets schedule -> enrolled in CS101 and CS102 -> sched1, sched2, sched3
        res = await ac.get(
            "/api/v1/student/schedule",
            headers={"Authorization": f"Bearer {auth_tokens['student1']}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 3
        # Sorted by study_date asc, start_time asc
        assert data[0]["class_code"] == "CS101"
        assert data[0]["course_name"] == "Lập trình Python"
        assert data[0]["teacher_name"] == "Nguyễn Văn Giảng"
        assert data[0]["room_name"] == "P.301"
        assert data[0]["session_order"] == 1

        # 2. Student 2 gets schedule -> only enrolled in CS102 -> 1 schedule
        res2 = await ac.get(
            "/api/v1/student/schedule",
            headers={"Authorization": f"Bearer {auth_tokens['student2']}"},
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert len(data2) == 1
        assert data2[0]["class_code"] == "CS102"


@pytest.mark.asyncio
async def test_student_get_attendance(test_session_maker, seeded_portal_data, auth_tokens):
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Student 1 gets attendance history
        res = await ac.get(
            "/api/v1/student/attendance",
            headers={"Authorization": f"Bearer {auth_tokens['student1']}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        att_item = data[0]
        assert att_item["class_code"] == "CS101"
        assert att_item["course_name"] == "Lập trình Python"
        assert att_item["status"] == "PRESENT"
        assert att_item["has_uniform"] is True
        assert att_item["note"] == "Đi học đúng giờ"
        assert "check_in_time" in att_item
        assert "check_out_time" in att_item

        # 2. Student 2 has no attendance yet
        res2 = await ac.get(
            "/api/v1/student/attendance",
            headers={"Authorization": f"Bearer {auth_tokens['student2']}"},
        )
        assert res2.status_code == 200
        assert len(res2.json()) == 0


@pytest.mark.asyncio
async def test_student_get_conduct_ledger(test_session_maker, seeded_portal_data, auth_tokens):
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Student 1 conduct ledger
        res = await ac.get(
            "/api/v1/student/conduct-ledger",
            headers={"Authorization": f"Bearer {auth_tokens['student1']}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total_point"] == 95
        assert len(data["items"]) == 2
        # Sorted newest first (pl2 had later created_at)
        assert data["items"][0]["point_delta"] == -7
        assert data["items"][0]["reason_code"] == "VIOLATION"
        assert data["items"][1]["point_delta"] == 2
        assert data["items"][1]["reason_code"] == "ATTENDANCE_FULL"

        # 2. Student 2 conduct ledger: 100 points, 0 entries
        res2 = await ac.get(
            "/api/v1/student/conduct-ledger",
            headers={"Authorization": f"Bearer {auth_tokens['student2']}"},
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["total_point"] == 100
        assert len(data2["items"]) == 0


@pytest.mark.asyncio
async def test_student_endpoints_role_protection(test_session_maker, seeded_portal_data, auth_tokens):
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Unauthenticated -> 401
        res = await ac.get("/api/v1/student/schedule")
        assert res.status_code == 401

        # 2. Teacher role -> 403
        res_t = await ac.get(
            "/api/v1/student/schedule",
            headers={"Authorization": f"Bearer {auth_tokens['teacher']}"},
        )
        assert res_t.status_code == 403

        # 3. Admin role -> 403
        res_a = await ac.get(
            "/api/v1/student/conduct-ledger",
            headers={"Authorization": f"Bearer {auth_tokens['admin']}"},
        )
        assert res_a.status_code == 403

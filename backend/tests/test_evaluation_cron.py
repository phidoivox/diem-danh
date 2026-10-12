from datetime import date, datetime, time, timedelta, timezone
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
from detect_ai.modules.leave.infrastructure.models import LeaveRequest, LeaveStatus
from detect_ai.modules.evaluation.infrastructure.models import PointLedger
from detect_ai.shared.kernel.system_setting import SystemSetting
from detect_ai.modules.identity.infrastructure.models import Role, StudentProfile, TeacherProfile, User
from detect_ai.modules.evaluation.application.nightly import run_nightly_evaluation


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

        # Admin
        admin = User(
            user_code="ADMIN01",
            full_name="Admin Test",
            email="admin@school.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=admin_role.id,
            is_active=True,
        )
        # Teacher
        teacher = User(
            user_code="GV001",
            full_name="GV Test",
            email="gv001@school.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=teacher_role.id,
            is_active=True,
        )
        session.add_all([admin, teacher])
        await session.commit()

        teacher_profile = TeacherProfile(
            user_id=teacher.id,
            department="CNTT",
            academic_title="ThS",
            office_room="A1-101",
        )
        session.add(teacher_profile)

        # 6 Students for various test cases
        students = []
        profiles = []
        for i in range(1, 7):
            sv = User(
                user_code=f"SV202600{i}",
                full_name=f"Sinh viên 0{i}",
                email=f"sv0{i}@student.edu.vn",
                password_hash=get_password_hash("Pass@123"),
                role_id=student_role.id,
                is_active=True,
            )
            students.append(sv)
        session.add_all(students)
        await session.commit()

        for sv in students:
            sp = StudentProfile(
                user_id=sv.id,
                total_point=100,
                class_name="CNTT-K24",
                major="KTPM",
            )
            profiles.append(sp)
        session.add_all(profiles)

        # Class
        test_class = Class(
            class_code="COMP101",
            course_name="Lập trình Cơ bản",
            teacher_id=teacher.id,
            semester="HK1-2026",
            total_sessions=15,
        )
        session.add(test_class)
        await session.commit()

        # Enroll students 1..6 into Class
        enrollments = [
            ClassStudent(class_id=test_class.id, student_id=sv.id) for sv in students
        ]
        session.add_all(enrollments)

        # Schedule for target date (e.g. 2026-09-17)
        study_date = date(2026, 9, 17)
        schedule = Schedule(
            class_id=test_class.id,
            room_name="A1-101",
            study_date=study_date,
            start_time=time(8, 0, 0),
            end_time=time(10, 0, 0),
            session_order=1,
        )
        session.add(schedule)

        # System settings
        settings = [
            SystemSetting(key="POINT_FULL_ATTENDANCE", value="2"),
            SystemSetting(key="POINT_LATE", value="-1"),
            SystemSetting(key="POINT_HALF_ABSENCE", value="-2"),
            SystemSetting(key="POINT_ABSENCE_WITHOUT_LEAVE", value="-5"),
            SystemSetting(key="POINT_UNIFORM_VIOLATION", value="-2"),
            SystemSetting(key="LATE_TOLERANCE_MINUTES", value="15"),
            SystemSetting(key="REQUIRE_CHECKOUT", value="true"),
        ]
        session.add_all(settings)
        await session.commit()

        return {
            "admin_id": admin.id,
            "teacher_id": teacher.id,
            "student_ids": [sv.id for sv in students],
            "class_id": test_class.id,
            "schedule_id": schedule.id,
            "study_date": study_date,
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
# TEST CASES
# =====================================================================


@pytest.mark.asyncio
async def test_case_1_full_attendance_on_time_with_uniform(test_session_maker, seeded_data):
    """Test Case 1: Đủ in/out, đúng giờ, có đồng phục -> PRESENT, kẹp trần 100 nên delta=0, total_point=100."""
    schedule_id = seeded_data["schedule_id"]
    student1_id = seeded_data["student_ids"][0]
    study_date = seeded_data["study_date"]

    async with test_session_maker() as session:
        att = Attendance(
            schedule_id=schedule_id,
            student_id=student1_id,
            check_in_time=datetime.combine(study_date, time(8, 5, 0), tzinfo=timezone.utc),
            check_out_time=datetime.combine(study_date, time(10, 0, 0), tzinfo=timezone.utc),
            has_uniform=True,
            status=AttendanceStatus.PRESENT,
            is_manual_override=False,
            is_evaluated=False,
        )
        session.add(att)
        await session.commit()

        # Run nightly evaluation
        result = await run_nightly_evaluation(session, target_date=study_date)
        assert result["total_records"] >= 1

        # Verify attendance record
        att_updated = (
            await session.execute(
                select(Attendance).where(
                    Attendance.schedule_id == schedule_id,
                    Attendance.student_id == student1_id,
                )
            )
        ).scalar_one()
        assert att_updated.status == AttendanceStatus.PRESENT
        assert att_updated.is_evaluated is True
        assert att_updated.evaluated_at is not None

        # Verify PointLedger
        ledger = (
            await session.execute(
                select(PointLedger).where(
                    PointLedger.schedule_id == schedule_id,
                    PointLedger.student_id == student1_id,
                )
            )
        ).scalar_one()
        assert ledger.point_delta == 0  # kẹp trần 100: 100+2 -> 100
        assert ledger.reason_code == "NIGHTLY_EVAL"
        assert "PRESENT" in ledger.description

        # Verify student total_point
        profile = (
            await session.execute(
                select(StudentProfile).where(StudentProfile.user_id == student1_id)
            )
        ).scalar_one()
        assert profile.total_point == 100


@pytest.mark.asyncio
async def test_case_2_missing_checkout_when_required(test_session_maker, seeded_data):
    """Test Case 2: Chỉ có in, thiếu out (khi REQUIRE_CHECKOUT=true) -> HALF_ABSENT, trừ 2 điểm (total_point = 98)."""
    schedule_id = seeded_data["schedule_id"]
    student2_id = seeded_data["student_ids"][1]
    study_date = seeded_data["study_date"]

    async with test_session_maker() as session:
        att = Attendance(
            schedule_id=schedule_id,
            student_id=student2_id,
            check_in_time=datetime.combine(study_date, time(8, 2, 0), tzinfo=timezone.utc),
            check_out_time=None,
            has_uniform=True,
            status=AttendanceStatus.PRESENT,
            is_manual_override=False,
            is_evaluated=False,
        )
        session.add(att)
        await session.commit()

        result = await run_nightly_evaluation(session, target_date=study_date)

        att_updated = (
            await session.execute(
                select(Attendance).where(
                    Attendance.schedule_id == schedule_id,
                    Attendance.student_id == student2_id,
                )
            )
        ).scalar_one()
        assert att_updated.status == AttendanceStatus.HALF_ABSENT
        assert att_updated.is_evaluated is True

        ledger = (
            await session.execute(
                select(PointLedger).where(
                    PointLedger.schedule_id == schedule_id,
                    PointLedger.student_id == student2_id,
                )
            )
        ).scalar_one()
        assert ledger.point_delta == -2
        assert ledger.reason_code == "NIGHTLY_EVAL"

        profile = (
            await session.execute(
                select(StudentProfile).where(StudentProfile.user_id == student2_id)
            )
        ).scalar_one()
        assert profile.total_point == 98


@pytest.mark.asyncio
async def test_case_3_no_check_in_or_out_absent(test_session_maker, seeded_data):
    """Test Case 3: Không quét cả in và out -> ABSENT, trừ 5 điểm (total_point = 95)."""
    schedule_id = seeded_data["schedule_id"]
    student3_id = seeded_data["student_ids"][2]
    study_date = seeded_data["study_date"]

    async with test_session_maker() as session:
        # Student 3 has NO attendance record created yet
        result = await run_nightly_evaluation(session, target_date=study_date)

        # Cron should auto-create Attendance with status ABSENT
        att_updated = (
            await session.execute(
                select(Attendance).where(
                    Attendance.schedule_id == schedule_id,
                    Attendance.student_id == student3_id,
                )
            )
        ).scalar_one()
        assert att_updated.status == AttendanceStatus.ABSENT
        assert att_updated.is_evaluated is True

        ledger = (
            await session.execute(
                select(PointLedger).where(
                    PointLedger.schedule_id == schedule_id,
                    PointLedger.student_id == student3_id,
                )
            )
        ).scalar_one()
        assert ledger.point_delta == -5
        assert ledger.reason_code == "NIGHTLY_EVAL"

        profile = (
            await session.execute(
                select(StudentProfile).where(StudentProfile.user_id == student3_id)
            )
        ).scalar_one()
        assert profile.total_point == 95


@pytest.mark.asyncio
async def test_case_4_late_and_uniform_violation(test_session_maker, seeded_data):
    """Test Case 4: Đến muộn -> LATE (-1). Vi phạm đồng phục -> trừ thêm 2 điểm (tổng delta = -3, total_point = 97)."""
    schedule_id = seeded_data["schedule_id"]
    student4_id = seeded_data["student_ids"][3]
    study_date = seeded_data["study_date"]

    async with test_session_maker() as session:
        # Late check-in: 08:20 (tolerance is 15 mins -> deadline 08:15)
        att = Attendance(
            schedule_id=schedule_id,
            student_id=student4_id,
            check_in_time=datetime.combine(study_date, time(8, 20, 0), tzinfo=timezone.utc),
            check_out_time=datetime.combine(study_date, time(10, 0, 0), tzinfo=timezone.utc),
            has_uniform=False,
            status=AttendanceStatus.LATE,
            is_manual_override=False,
            is_evaluated=False,
        )
        session.add(att)
        await session.commit()

        result = await run_nightly_evaluation(session, target_date=study_date)

        att_updated = (
            await session.execute(
                select(Attendance).where(
                    Attendance.schedule_id == schedule_id,
                    Attendance.student_id == student4_id,
                )
            )
        ).scalar_one()
        assert att_updated.status == AttendanceStatus.LATE
        assert att_updated.is_evaluated is True

        ledger = (
            await session.execute(
                select(PointLedger).where(
                    PointLedger.schedule_id == schedule_id,
                    PointLedger.student_id == student4_id,
                )
            )
        ).scalar_one()
        assert ledger.point_delta == -3  # -1 (late) + -2 (uniform)
        assert ledger.reason_code == "NIGHTLY_EVAL"

        profile = (
            await session.execute(
                select(StudentProfile).where(StudentProfile.user_id == student4_id)
            )
        ).scalar_one()
        assert profile.total_point == 97


@pytest.mark.asyncio
async def test_case_5_approved_leave_request_excused(test_session_maker, seeded_data):
    """Test Case 5: Đơn xin nghỉ phép đã duyệt -> EXCUSED, 0 điểm, không trừ điểm."""
    schedule_id = seeded_data["schedule_id"]
    student5_id = seeded_data["student_ids"][4]
    study_date = seeded_data["study_date"]

    async with test_session_maker() as session:
        # Approved leave request exists
        leave = LeaveRequest(
            student_id=student5_id,
            schedule_id=schedule_id,
            reason="Bị ốm có giấy khám",
            status=LeaveStatus.APPROVED,
            reviewed_by=seeded_data["teacher_id"],
        )
        session.add(leave)
        await session.commit()

        result = await run_nightly_evaluation(session, target_date=study_date)

        att_updated = (
            await session.execute(
                select(Attendance).where(
                    Attendance.schedule_id == schedule_id,
                    Attendance.student_id == student5_id,
                )
            )
        ).scalar_one()
        assert att_updated.status == AttendanceStatus.EXCUSED
        assert att_updated.is_evaluated is True

        ledger = (
            await session.execute(
                select(PointLedger).where(
                    PointLedger.schedule_id == schedule_id,
                    PointLedger.student_id == student5_id,
                )
            )
        ).scalar_one()
        assert ledger.point_delta == 0
        assert ledger.reason_code == "NIGHTLY_EVAL"

        profile = (
            await session.execute(
                select(StudentProfile).where(StudentProfile.user_id == student5_id)
            )
        ).scalar_one()
        assert profile.total_point == 100


@pytest.mark.asyncio
async def test_case_6_teacher_manual_override_respected(test_session_maker, seeded_data):
    """Test Case 6: Giáo viên sửa tay (is_manual_override = True) -> cron giữ nguyên status của giáo viên."""
    schedule_id = seeded_data["schedule_id"]
    student6_id = seeded_data["student_ids"][5]
    study_date = seeded_data["study_date"]

    async with test_session_maker() as session:
        # Teacher manually marked student as PRESENT even though check_in_time is None
        att = Attendance(
            schedule_id=schedule_id,
            student_id=student6_id,
            check_in_time=None,
            check_out_time=None,
            has_uniform=True,
            status=AttendanceStatus.PRESENT,
            is_manual_override=True,
            note="Giáo viên xác nhận tham gia trực tiếp",
            is_evaluated=False,
        )
        session.add(att)
        await session.commit()

        result = await run_nightly_evaluation(session, target_date=study_date)

        att_updated = (
            await session.execute(
                select(Attendance).where(
                    Attendance.schedule_id == schedule_id,
                    Attendance.student_id == student6_id,
                )
            )
        ).scalar_one()
        # Must retain PRESENT status set by teacher
        assert att_updated.status == AttendanceStatus.PRESENT
        assert att_updated.is_evaluated is True

        ledger = (
            await session.execute(
                select(PointLedger).where(
                    PointLedger.schedule_id == schedule_id,
                    PointLedger.student_id == student6_id,
                )
            )
        ).scalar_one()
        assert ledger.point_delta == 0  # kẹp trần 100: 100+2 -> 100
        assert ledger.reason_code == "NIGHTLY_EVAL"

        profile = (
            await session.execute(
                select(StudentProfile).where(StudentProfile.user_id == student6_id)
            )
        ).scalar_one()
        assert profile.total_point == 100


@pytest.mark.asyncio
async def test_case_7_idempotency_second_run(test_session_maker, seeded_data):
    """Test Case 7: Tính Idempotent: Chạy lại lần 2 cho cùng 1 ngày -> Bỏ qua bản ghi đã is_evaluated=True, không sinh thêm ledger và không trừ điểm lặp lại!"""
    study_date = seeded_data["study_date"]
    schedule_id = seeded_data["schedule_id"]
    student1_id = seeded_data["student_ids"][0]

    async with test_session_maker() as session:
        # First evaluation
        result1 = await run_nightly_evaluation(session, target_date=study_date)
        assert result1["total_records"] > 0

        ledgers_after_run1 = (
            await session.execute(select(PointLedger))
        ).scalars().all()
        ledger_count_1 = len(ledgers_after_run1)
        assert ledger_count_1 > 0

        profile_after_run1 = (
            await session.execute(
                select(StudentProfile).where(StudentProfile.user_id == student1_id)
            )
        ).scalar_one()
        point_after_run1 = profile_after_run1.total_point

        # Second evaluation for the SAME date
        result2 = await run_nightly_evaluation(session, target_date=study_date)
        assert result2["total_records"] == 0
        assert result2["students_evaluated"] == 0

        ledgers_after_run2 = (
            await session.execute(select(PointLedger))
        ).scalars().all()
        ledger_count_2 = len(ledgers_after_run2)
        assert ledger_count_2 == ledger_count_1  # No extra ledger created!

        profile_after_run2 = (
            await session.execute(
                select(StudentProfile).where(StudentProfile.user_id == student1_id)
            )
        ).scalar_one()
        assert profile_after_run2.total_point == point_after_run1  # No points double-deducted!


@pytest.mark.asyncio
async def test_case_8_endpoint_run_now_rbac(client: AsyncClient, seeded_data):
    """Test Case 8: Endpoint POST /api/v1/admin/evaluation/run-now (Admin: 200, Teacher/Student: 403, No token: 401)."""
    admin_headers = make_auth_header("ADMIN01", "ADMIN")
    teacher_headers = make_auth_header("GV001", "TEACHER")
    student_headers = make_auth_header("SV2026001", "STUDENT")

    target_date_str = str(seeded_data["study_date"])

    # 1. Unauthenticated -> 401
    resp_unauth = await client.post(f"/api/v1/admin/evaluation/run-now?target_date={target_date_str}")
    assert resp_unauth.status_code == 401

    # 2. Student -> 403
    resp_student = await client.post(
        f"/api/v1/admin/evaluation/run-now?target_date={target_date_str}",
        headers=student_headers,
    )
    assert resp_student.status_code == 403

    # 3. Teacher -> 403
    resp_teacher = await client.post(
        f"/api/v1/admin/evaluation/run-now?target_date={target_date_str}",
        headers=teacher_headers,
    )
    assert resp_teacher.status_code == 403

    # 4. Admin -> 200 OK
    resp_admin = await client.post(
        f"/api/v1/admin/evaluation/run-now?target_date={target_date_str}",
        headers=admin_headers,
    )
    assert resp_admin.status_code == 200
    data = resp_admin.json()
    assert "target_date" in data
    assert "schedules_evaluated" in data
    assert "students_evaluated" in data
    assert "total_records" in data
    assert data["target_date"] == target_date_str


@pytest.mark.asyncio
async def test_case_9_require_checkout_false(test_session_maker, seeded_data):
    """Test Case 9: Khi REQUIRE_CHECKOUT=false, có check-in nhưng không có check-out vẫn được PRESENT (kẹp trần 100 nên delta=0)."""
    study_date = date(2026, 9, 18)
    schedule_id = seeded_data["schedule_id"]
    student1_id = seeded_data["student_ids"][0]

    async with test_session_maker() as session:
        # Change REQUIRE_CHECKOUT setting to false
        stmt_setting = select(SystemSetting).where(SystemSetting.key == "REQUIRE_CHECKOUT")
        setting = (await session.execute(stmt_setting)).scalar_one()
        setting.value = "false"

        # Create new schedule on 2026-09-18
        schedule2 = Schedule(
            class_id=seeded_data["class_id"],
            room_name="A1-102",
            study_date=study_date,
            start_time=time(8, 0, 0),
            end_time=time(10, 0, 0),
            session_order=2,
        )
        session.add(schedule2)
        await session.commit()

        # Student only checks in on time, no checkout
        att = Attendance(
            schedule_id=schedule2.id,
            student_id=student1_id,
            check_in_time=datetime.combine(study_date, time(8, 5, 0), tzinfo=timezone.utc),
            check_out_time=None,
            has_uniform=True,
            status=AttendanceStatus.PRESENT,
            is_manual_override=False,
            is_evaluated=False,
        )
        session.add(att)
        await session.commit()

        result = await run_nightly_evaluation(session, target_date=study_date)

        att_updated = (
            await session.execute(
                select(Attendance).where(
                    Attendance.schedule_id == schedule2.id,
                    Attendance.student_id == student1_id,
                )
            )
        ).scalar_one()
        assert att_updated.status == AttendanceStatus.PRESENT
        assert att_updated.is_evaluated is True

        ledger = (
            await session.execute(
                select(PointLedger).where(
                    PointLedger.schedule_id == schedule2.id,
                    PointLedger.student_id == student1_id,
                )
            )
        ).scalar_one()
        assert ledger.point_delta == 0  # kẹp trần 100: 100+2 -> 100

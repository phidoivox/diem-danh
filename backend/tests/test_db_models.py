import shutil
from pathlib import Path

import pytest
from datetime import date, time, datetime, timezone
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from detect_ai.shared.kernel.database import Base
from detect_ai.modules.identity.infrastructure.models import Role, User, StudentProfile, TeacherProfile
from detect_ai.modules.academic.infrastructure.models import Class, ClassStudent, Schedule
from detect_ai.modules.attendance.infrastructure.models import Attendance, AttendanceStatus
from detect_ai.modules.leave.infrastructure.models import LeaveRequest, LeaveStatus
from detect_ai.modules.evaluation.infrastructure.models import PointLedger
from detect_ai.shared.kernel.system_setting import SystemSetting


@pytest_asyncio.fixture
async def test_db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    from sqlalchemy import event
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_roles_and_users(test_db_session: AsyncSession):
    # 1. Create Roles
    admin_role = Role(role_name="ADMIN")
    teacher_role = Role(role_name="TEACHER")
    student_role = Role(role_name="STUDENT")
    test_db_session.add_all([admin_role, teacher_role, student_role])
    await test_db_session.commit()

    # 2. Create Admin User
    admin_user = User(
        user_code="ADMIN01",
        full_name="System Administrator",
        email="admin@school.edu.vn",
        password_hash="hashed_pw_admin",
        role_id=admin_role.id,
    )
    test_db_session.add(admin_user)
    await test_db_session.commit()
    await test_db_session.refresh(admin_user)

    assert admin_user.id is not None
    assert admin_user.role.role_name == "ADMIN"
    assert admin_user.is_active is True
    assert admin_user.deleted_at is None


@pytest.mark.asyncio
async def test_user_student_profile_1_to_1(test_db_session: AsyncSession):
    student_role = Role(role_name="STUDENT")
    test_db_session.add(student_role)
    await test_db_session.commit()

    student_user = User(
        user_code="SV2026001",
        full_name="Tran Thi Mai",
        email="maitt@student.edu.vn",
        password_hash="hashed_pw",
        role_id=student_role.id,
    )
    test_db_session.add(student_user)
    await test_db_session.commit()

    profile = StudentProfile(
        user_id=student_user.id,
        face_embedding="[0.12, 0.34, 0.56]",
        total_point=100,
        class_name="CNTT-K24A",
        major="Computer Science",
    )
    test_db_session.add(profile)
    await test_db_session.commit()

    # Query back and verify 1-1 relationship
    stmt = select(User).where(User.id == student_user.id)
    res = await test_db_session.execute(stmt)
    u = res.scalar_one()

    assert u.student_profile is not None
    assert u.student_profile.total_point == 100
    assert u.student_profile.class_name == "CNTT-K24A"
    assert u.student_profile.user.user_code == "SV2026001"

    # Test cascade delete: deleting user should delete student_profile
    await test_db_session.delete(u)
    await test_db_session.commit()

    prof_check = await test_db_session.execute(
        select(StudentProfile).where(StudentProfile.id == profile.id)
    )
    assert prof_check.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_user_teacher_profile_1_to_1(test_db_session: AsyncSession):
    teacher_role = Role(role_name="TEACHER")
    test_db_session.add(teacher_role)
    await test_db_session.commit()

    teacher_user = User(
        user_code="GV01",
        full_name="Nguyen Van A",
        email="nguyenvana@school.edu.vn",
        password_hash="hashed_pw",
        role_id=teacher_role.id,
    )
    test_db_session.add(teacher_user)
    await test_db_session.commit()

    profile = TeacherProfile(
        user_id=teacher_user.id,
        department="Information Technology",
        academic_title="PhD",
        office_room="A1-204",
    )
    test_db_session.add(profile)
    await test_db_session.commit()

    stmt = select(User).where(User.id == teacher_user.id)
    res = await test_db_session.execute(stmt)
    u = res.scalar_one()

    assert u.teacher_profile is not None
    assert u.teacher_profile.department == "Information Technology"
    assert u.teacher_profile.academic_title == "PhD"
    assert u.teacher_profile.office_room == "A1-204"


@pytest.mark.asyncio
async def test_classes_and_schedules(test_db_session: AsyncSession):
    teacher_role = Role(role_name="TEACHER")
    student_role = Role(role_name="STUDENT")
    test_db_session.add_all([teacher_role, student_role])
    await test_db_session.commit()

    teacher = User(
        user_code="GV02",
        full_name="Le Van B",
        email="levanb@school.edu.vn",
        password_hash="hashed_pw",
        role_id=teacher_role.id,
    )
    student = User(
        user_code="SV2026002",
        full_name="Hoang Van C",
        email="hoangvanc@student.edu.vn",
        password_hash="hashed_pw",
        role_id=student_role.id,
    )
    test_db_session.add_all([teacher, student])
    await test_db_session.commit()

    # Create Class
    clazz = Class(
        class_code="CS101.1",
        course_name="Introduction to AI",
        teacher_id=teacher.id,
        semester="HK1_2026",
        total_sessions=15,
    )
    test_db_session.add(clazz)
    await test_db_session.commit()

    # Enroll student
    enrollment = ClassStudent(class_id=clazz.id, student_id=student.id)
    test_db_session.add(enrollment)
    await test_db_session.commit()

    # Create Schedule
    sched = Schedule(
        class_id=clazz.id,
        room_name="A101",
        study_date=date(2026, 9, 20),
        start_time=time(7, 30),
        end_time=time(11, 0),
        session_order=1,
    )
    test_db_session.add(sched)
    await test_db_session.commit()

    assert sched.id is not None
    assert sched.clazz.class_code == "CS101.1"


@pytest.mark.asyncio
async def test_attendance_and_unique_constraint(test_db_session: AsyncSession):
    teacher_role = Role(role_name="TEACHER")
    student_role = Role(role_name="STUDENT")
    test_db_session.add_all([teacher_role, student_role])
    await test_db_session.commit()

    teacher = User(user_code="GV03", full_name="T3", email="t3@school.edu.vn", password_hash="pw", role_id=teacher_role.id)
    student = User(user_code="SV03", full_name="S3", email="s3@student.edu.vn", password_hash="pw", role_id=student_role.id)
    test_db_session.add_all([teacher, student])
    await test_db_session.commit()

    clazz = Class(class_code="MATH101", course_name="Calculus", teacher_id=teacher.id, semester="HK1_2026")
    test_db_session.add(clazz)
    await test_db_session.commit()

    sched = Schedule(
        class_id=clazz.id,
        room_name="B201",
        study_date=date(2026, 9, 21),
        start_time=time(13, 0),
        end_time=time(16, 30),
        session_order=1,
    )
    test_db_session.add(sched)
    await test_db_session.commit()

    att = Attendance(
        schedule_id=sched.id,
        student_id=student.id,
        check_in_time=datetime.now(timezone.utc),
        status=AttendanceStatus.PRESENT,
        has_uniform=True,
    )
    test_db_session.add(att)
    await test_db_session.commit()
    assert att.id is not None
    assert att.status == AttendanceStatus.PRESENT
    assert att.is_evaluated is False
    assert att.is_manual_override is False

    # Attempting duplicate attendance for same (schedule_id, student_id) should fail
    dup_att = Attendance(
        schedule_id=sched.id,
        student_id=student.id,
        status=AttendanceStatus.LATE,
    )
    test_db_session.add(dup_att)
    with pytest.raises(IntegrityError):
        await test_db_session.commit()
    await test_db_session.rollback()


@pytest.mark.asyncio
async def test_leave_request_and_point_ledger(test_db_session: AsyncSession):
    student_role = Role(role_name="STUDENT")
    teacher_role = Role(role_name="TEACHER")
    test_db_session.add_all([student_role, teacher_role])
    await test_db_session.commit()

    student = User(user_code="SV04", full_name="S4", email="s4@student.edu.vn", password_hash="pw", role_id=student_role.id)
    teacher = User(user_code="GV04", full_name="T4", email="t4@school.edu.vn", password_hash="pw", role_id=teacher_role.id)
    test_db_session.add_all([student, teacher])
    await test_db_session.commit()

    clazz = Class(class_code="PHYS101", course_name="Physics", teacher_id=teacher.id, semester="HK1_2026")
    test_db_session.add(clazz)
    await test_db_session.commit()

    sched = Schedule(
        class_id=clazz.id,
        room_name="Lab1",
        study_date=date(2026, 9, 22),
        start_time=time(8, 0),
        end_time=time(11, 30),
        session_order=2,
    )
    test_db_session.add(sched)
    await test_db_session.commit()

    # Leave Request
    lr = LeaveRequest(
        schedule_id=sched.id,
        student_id=student.id,
        reason="Got fever with doctor note",
        proof_image="https://example.com/proof.jpg",
        status=LeaveStatus.PENDING,
    )
    test_db_session.add(lr)
    await test_db_session.commit()
    assert lr.id is not None
    assert lr.status == LeaveStatus.PENDING

    # Point Ledger entry
    entry = PointLedger(
        student_id=student.id,
        schedule_id=sched.id,
        point_delta=-5,
        reason_code="NIGHTLY_EVAL",
        description="Absent without leave",
    )
    test_db_session.add(entry)
    await test_db_session.commit()
    assert entry.id is not None
    assert entry.point_delta == -5
    assert entry.reason_code == "NIGHTLY_EVAL"


@pytest.mark.asyncio
async def test_system_settings(test_db_session: AsyncSession):
    setting = SystemSetting(
        key="POINT_FULL_ATTENDANCE",
        value="2",
        description="Points awarded for full attendance and proper uniform",
    )
    test_db_session.add(setting)
    await test_db_session.commit()

    res = await test_db_session.execute(
        select(SystemSetting).where(SystemSetting.key == "POINT_FULL_ATTENDANCE")
    )
    s = res.scalar_one()
    assert s.value == "2"


@pytest.mark.asyncio
async def test_schedule_check_constraint(test_db_session: AsyncSession):
    teacher_role = Role(role_name="TEACHER")
    test_db_session.add(teacher_role)
    await test_db_session.commit()

    teacher = User(user_code="GV05", full_name="T5", email="t5@school.edu.vn", password_hash="pw", role_id=teacher_role.id)
    test_db_session.add(teacher)
    await test_db_session.commit()

    clazz = Class(class_code="ENG101", course_name="English", teacher_id=teacher.id, semester="HK1_2026")
    test_db_session.add(clazz)
    await test_db_session.commit()

    # Invalid schedule: start_time (10:00) >= end_time (09:00)
    invalid_sched = Schedule(
        class_id=clazz.id,
        room_name="A102",
        study_date=date(2026, 9, 23),
        start_time=time(10, 0),
        end_time=time(9, 0),
        session_order=1,
    )
    test_db_session.add(invalid_sched)
    with pytest.raises(IntegrityError):
        await test_db_session.commit()
    await test_db_session.rollback()


@pytest.mark.asyncio
async def test_supabase_storage_local_fallback():
    from detect_ai.shared.kernel.supabase import SupabaseStorageHelper

    # Thư mục tạm nằm trong repo, tạo với quyền mặc định (không dùng fixture tmp_path):
    # fixture này tạo thư mục với mode 0o700 nên bị một số môi trường sandbox chặn truy cập.
    storage_root = Path(__file__).resolve().parents[1] / "data" / "_test_storage_tmp"
    shutil.rmtree(storage_root, ignore_errors=True)
    storage_root.mkdir(parents=True, exist_ok=True)

    try:
        storage = SupabaseStorageHelper(supabase_url="", service_key="", storage_dir=storage_root)
        url = await storage.upload_file(
            bucket=SupabaseStorageHelper.BUCKET_LEAVE_PROOFS,
            path="test_proof.png",
            content=b"fake-image-bytes",
            content_type="image/png",
        )
        assert url == "/api/v1/files/leave-proof/test_proof.png"

        pub_url = await storage.get_public_url(SupabaseStorageHelper.BUCKET_LEAVE_PROOFS, "test_proof.png")
        assert pub_url == "/api/v1/files/leave-proof/test_proof.png"

        deleted = await storage.delete_file(SupabaseStorageHelper.BUCKET_LEAVE_PROOFS, "test_proof.png")
        assert deleted is True

        # Delete non-existent
        deleted_again = await storage.delete_file(SupabaseStorageHelper.BUCKET_LEAVE_PROOFS, "test_proof.png")
        assert deleted_again is False
    finally:
        shutil.rmtree(storage_root, ignore_errors=True)


@pytest.mark.asyncio
async def test_init_db_execution():
    from detect_ai.shared.kernel.database import init_db
    # Verify init_db runs cleanly
    await init_db()


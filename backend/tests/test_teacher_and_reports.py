import io
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import openpyxl
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
from detect_ai.modules.identity.infrastructure.models import Role, StudentProfile, TeacherProfile, User
from detect_ai.modules.reporting.application import build as report_service


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
        admin_user = User(
            user_code="ADMIN01",
            full_name="Quản Trị Viên",
            email="admin@school.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=admin_role.id,
            is_active=True,
        )

        # Teachers
        teacher1 = User(
            user_code="GV001",
            full_name="Nguyễn Văn Giảng 1",
            email="gv1@school.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=teacher_role.id,
            is_active=True,
        )
        teacher2 = User(
            user_code="GV002",
            full_name="Trần Thị Giảng 2",
            email="gv2@school.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=teacher_role.id,
            is_active=True,
        )
        session.add_all([admin_user, teacher1, teacher2])
        await session.commit()
        await session.refresh(admin_user)
        await session.refresh(teacher1)
        await session.refresh(teacher2)

        tp1 = TeacherProfile(user_id=teacher1.id, department="CNTT", academic_title="ThS", office_room="A101")
        tp2 = TeacherProfile(user_id=teacher2.id, department="CNTT", academic_title="TS", office_room="A102")
        session.add_all([tp1, tp2])

        # Students
        student1 = User(
            user_code="SV001",
            full_name="Lê Văn Sinh Viên 1",
            email="sv1@student.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=student_role.id,
            is_active=True,
        )
        student2 = User(
            user_code="SV002",
            full_name="Phạm Thị Sinh Viên 2",
            email="sv2@student.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=student_role.id,
            is_active=True,
        )
        student3 = User(
            user_code="SV003",
            full_name="Hoàng Văn Sinh Viên 3",
            email="sv3@student.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=student_role.id,
            is_active=True,
        )
        session.add_all([student1, student2, student3])
        await session.commit()
        await session.refresh(student1)
        await session.refresh(student2)
        await session.refresh(student3)

        sp1 = StudentProfile(user_id=student1.id, class_name="D20CNTT1", major="CNTT", total_point=100)
        sp2 = StudentProfile(user_id=student2.id, class_name="D20CNTT1", major="CNTT", total_point=100)
        sp3 = StudentProfile(user_id=student3.id, class_name="D20CNTT2", major="CNTT", total_point=100)
        session.add_all([sp1, sp2, sp3])

        # Classes
        # Class 1: taught by teacher1, 15 sessions
        class1 = Class(
            class_code="CS101",
            course_name="Lập trình Python",
            teacher_id=teacher1.id,
            semester="2026.1",
            total_sessions=15,
        )
        # Class 2: taught by teacher2, 15 sessions
        class2 = Class(
            class_code="CS102",
            course_name="Cơ sở dữ liệu",
            teacher_id=teacher2.id,
            semester="2026.1",
            total_sessions=15,
        )
        session.add_all([class1, class2])
        await session.commit()
        await session.refresh(class1)
        await session.refresh(class2)

        # Enrollments
        # class1 has student1, student2, student3
        # class2 has student1
        cs1 = ClassStudent(class_id=class1.id, student_id=student1.id)
        cs2 = ClassStudent(class_id=class1.id, student_id=student2.id)
        cs3 = ClassStudent(class_id=class1.id, student_id=student3.id)
        cs4 = ClassStudent(class_id=class2.id, student_id=student1.id)
        session.add_all([cs1, cs2, cs3, cs4])
        await session.commit()

        # Schedules and Attendances for Class 1:
        # 3 past sessions (study_date <= today) to evaluate ban criteria
        today = date.today()
        sched_past1 = Schedule(
            class_id=class1.id,
            room_name="A101",
            study_date=today - timedelta(days=3),
            start_time=time(8, 0),
            end_time=time(11, 30),
            session_order=1,
        )
        sched_past2 = Schedule(
            class_id=class1.id,
            room_name="A101",
            study_date=today - timedelta(days=2),
            start_time=time(8, 0),
            end_time=time(11, 30),
            session_order=2,
        )
        sched_past3 = Schedule(
            class_id=class1.id,
            room_name="A101",
            study_date=today - timedelta(days=1),
            start_time=time(8, 0),
            end_time=time(11, 30),
            session_order=3,
        )
        # Today's schedule for live attendance (kết thúc 23:30 để test
        # chạy được mọi giờ trong ngày; logic khung giờ do test_current_session
        # và test_kiosk_window bao phủ với giờ cố định)
        sched_today = Schedule(
            class_id=class1.id,
            room_name="A101",
            study_date=today,
            start_time=time(0, 0),
            end_time=time(23, 59),
            session_order=4,
        )

        # Schedule for Class 2
        sched_class2 = Schedule(
            class_id=class2.id,
            room_name="B202",
            study_date=today - timedelta(days=1),
            start_time=time(8, 0),
            end_time=time(11, 30),
            session_order=1,
        )

        session.add_all([sched_past1, sched_past2, sched_past3, sched_today, sched_class2])
        await session.commit()
        await session.refresh(sched_past1)
        await session.refresh(sched_past2)
        await session.refresh(sched_past3)
        await session.refresh(sched_today)
        await session.refresh(sched_class2)

        # Attendances for past sessions in Class 1:
        # Student 1: 3 ABSENT -> 3 / 15 = 20% -> BANNED
        att_s1_p1 = Attendance(
            schedule_id=sched_past1.id,
            student_id=student1.id,
            status=AttendanceStatus.ABSENT,
            is_evaluated=True,
        )
        att_s1_p2 = Attendance(
            schedule_id=sched_past2.id,
            student_id=student1.id,
            status=AttendanceStatus.ABSENT,
            is_evaluated=True,
        )
        att_s1_p3 = Attendance(
            schedule_id=sched_past3.id,
            student_id=student1.id,
            status=AttendanceStatus.ABSENT,
            is_evaluated=True,
        )

        # Student 2: 3 EXCUSED -> 0 absent converted -> NOT BANNED
        att_s2_p1 = Attendance(
            schedule_id=sched_past1.id,
            student_id=student2.id,
            status=AttendanceStatus.EXCUSED,
            is_evaluated=True,
        )
        att_s2_p2 = Attendance(
            schedule_id=sched_past2.id,
            student_id=student2.id,
            status=AttendanceStatus.EXCUSED,
            is_evaluated=True,
        )
        att_s2_p3 = Attendance(
            schedule_id=sched_past3.id,
            student_id=student2.id,
            status=AttendanceStatus.EXCUSED,
            is_evaluated=True,
        )

        # Student 3: 2 HALF_ABSENT + 1 PRESENT -> V = 2 * 0.5 = 1.0 -> rate_semester = 1/15 = 6.67%
        att_s3_p1 = Attendance(
            schedule_id=sched_past1.id,
            student_id=student3.id,
            status=AttendanceStatus.HALF_ABSENT,
            is_evaluated=True,
        )
        att_s3_p2 = Attendance(
            schedule_id=sched_past2.id,
            student_id=student3.id,
            status=AttendanceStatus.HALF_ABSENT,
            is_evaluated=True,
        )
        att_s3_p3 = Attendance(
            schedule_id=sched_past3.id,
            student_id=student3.id,
            status=AttendanceStatus.PRESENT,
            is_evaluated=True,
        )

        # Attendances for Today's session:
        # Student 1: Checked in on time, uniform OK
        att_today_s1 = Attendance(
            schedule_id=sched_today.id,
            student_id=student1.id,
            check_in_time=datetime.now(timezone.utc),
            has_uniform=True,
            status=AttendanceStatus.PRESENT,
            is_evaluated=False,
        )
        # Student 2: Not checked in yet (EXCUSED)
        att_today_s2 = Attendance(
            schedule_id=sched_today.id,
            student_id=student2.id,
            has_uniform=True,
            status=AttendanceStatus.EXCUSED,
            is_evaluated=False,
        )
        # Student 3: Checked in but uniform violation
        att_today_s3 = Attendance(
            schedule_id=sched_today.id,
            student_id=student3.id,
            check_in_time=datetime.now(timezone.utc),
            has_uniform=False,
            status=AttendanceStatus.PRESENT,
            is_evaluated=False,
        )

        # Class 2 attendance for student 1: PRESENT
        att_c2_s1 = Attendance(
            schedule_id=sched_class2.id,
            student_id=student1.id,
            check_in_time=datetime.now(timezone.utc),
            has_uniform=True,
            status=AttendanceStatus.PRESENT,
            is_evaluated=True,
        )

        session.add_all([
            att_s1_p1, att_s1_p2, att_s1_p3,
            att_s2_p1, att_s2_p2, att_s2_p3,
            att_s3_p1, att_s3_p2, att_s3_p3,
            att_today_s1, att_today_s2, att_today_s3,
            att_c2_s1,
        ])
        await session.commit()

        yield {
            "admin_user": admin_user,
            "teacher1": teacher1,
            "teacher2": teacher2,
            "student1": student1,
            "student2": student2,
            "student3": student3,
            "class1": class1,
            "class2": class2,
            "sched_today": sched_today,
            "att_today_s2": att_today_s2,
        }


@pytest.fixture
def auth_tokens(seeded_data):
    def make_token(user):
        return create_access_token({"sub": str(user.id), "role": user.role.role_name})

    return {
        "admin": make_token(seeded_data["admin_user"]),
        "teacher1": make_token(seeded_data["teacher1"]),
        "teacher2": make_token(seeded_data["teacher2"]),
        "student1": make_token(seeded_data["student1"]),
    }


@pytest.mark.asyncio
async def test_teacher_get_classes(test_session_maker, seeded_data, auth_tokens):
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Teacher 1 requests classes -> only sees class1
        res = await ac.get(
            "/api/v1/teacher/classes",
            headers={"Authorization": f"Bearer {auth_tokens['teacher1']}"},
        )
        assert res.status_code == 200
        classes = res.json()
        assert len(classes) == 1
        assert classes[0]["class_code"] == "CS101"
        assert classes[0]["course_name"] == "Lập trình Python"
        assert classes[0]["student_count"] == 3

        # 2. Teacher 2 requests classes -> only sees class2
        res2 = await ac.get(
            "/api/v1/teacher/classes",
            headers={"Authorization": f"Bearer {auth_tokens['teacher2']}"},
        )
        assert res2.status_code == 200
        classes2 = res2.json()
        assert len(classes2) == 1
        assert classes2[0]["class_code"] == "CS102"
        assert classes2[0]["student_count"] == 1

        # 3. Student requests teacher classes -> 403 Forbidden
        res3 = await ac.get(
            "/api/v1/teacher/classes",
            headers={"Authorization": f"Bearer {auth_tokens['student1']}"},
        )
        assert res3.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_teacher_live_attendance(test_session_maker, seeded_data, auth_tokens):
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    class1_id = seeded_data["class1"].id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Teacher 1 checks live attendance of class1
        res = await ac.get(
            f"/api/v1/teacher/classes/{class1_id}/live-attendance",
            headers={"Authorization": f"Bearer {auth_tokens['teacher1']}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total_students"] == 3
        assert data["checked_in_count"] == 2  # student1 and student3
        assert data["absent_count"] == 1       # student2
        assert data["uniform_violation_count"] == 1  # student3

        # Check student details in list
        students = data["students"]
        assert len(students) == 3
        student_codes = [s["student_code"] for s in students]
        assert "SV001" in student_codes
        assert "SV002" in student_codes
        assert "SV003" in student_codes

        # 2. Teacher 2 tries to view class1 live attendance -> 403 Forbidden
        res_t2 = await ac.get(
            f"/api/v1/teacher/classes/{class1_id}/live-attendance",
            headers={"Authorization": f"Bearer {auth_tokens['teacher2']}"},
        )
        assert res_t2.status_code == 403

        # 3. Non-existent class -> 404
        res_404 = await ac.get(
            "/api/v1/teacher/classes/99999/live-attendance",
            headers={"Authorization": f"Bearer {auth_tokens['teacher1']}"},
        )
        assert res_404.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_teacher_manual_override(test_session_maker, seeded_data, auth_tokens):
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    att_today_s2_id = seeded_data["att_today_s2"].id
    teacher1_id = seeded_data["teacher1"].id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Teacher 2 tries to manual-override attendance in Class 1 -> 403 Forbidden
        res_t2 = await ac.put(
            f"/api/v1/teacher/attendance/{att_today_s2_id}/manual-override",
            json={"status": "PRESENT", "note": "GV2 can thiệp trái phép"},
            headers={"Authorization": f"Bearer {auth_tokens['teacher2']}"},
        )
        assert res_t2.status_code == 403

        # 2. Teacher 1 overrides attendance for Student 2: marks PRESENT with note
        res_t1 = await ac.put(
            f"/api/v1/teacher/attendance/{att_today_s2_id}/manual-override",
            json={"status": "PRESENT", "note": "Sinh viên bổ sung giấy phép trực tiếp"},
            headers={"Authorization": f"Bearer {auth_tokens['teacher1']}"},
        )
        assert res_t1.status_code == 200
        data = res_t1.json()
        assert data["status"] == "PRESENT"
        assert data["note"] == "Sinh viên bổ sung giấy phép trực tiếp"
        assert data["is_manual_override"] is True
        assert data["updated_by"] == teacher1_id

    # Verify directly in DB
    async with test_session_maker() as session:
        att = await session.get(Attendance, att_today_s2_id)
        assert att.status == AttendanceStatus.PRESENT
        assert att.is_manual_override is True
        assert att.updated_by == teacher1_id
        assert att.note == "Sinh viên bổ sung giấy phép trực tiếp"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_exam_ban_calculation(test_session_maker, seeded_data, auth_tokens, monkeypatch):
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    # Báo cáo chỉ tính buổi đã KẾT THÚC (giờ VN). Cố định "bây giờ" = 23:59 hôm nay để
    # buổi 00:00-23:59 hôm nay chắc chắn đã kết thúc ⇒ test không phụ thuộc giờ chạy.
    # Khung giờ cả ngày: kiosk test nào cũng thấy buổi đang mở, báo cáo nào cũng thấy đã xong.
    # (khôi phục drift 22:53 của user — giữ nguyên logic, chỉ rewire import ở Task 9c)
    monkeypatch.setattr(
        report_service,
        "now_vn",
        lambda: datetime.combine(date.today(), time(23, 59), tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")),
    )

    app.dependency_overrides[get_db] = override_get_db
    class1_id = seeded_data["class1"].id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Teacher 1 queries exam-ban report
        res = await ac.get(
            f"/api/v1/teacher/classes/{class1_id}/exam-ban-report",
            headers={"Authorization": f"Bearer {auth_tokens['teacher1']}"},
        )
        assert res.status_code == 200
        report = res.json()

        assert report["class_id"] == class1_id
        assert report["class_code"] == "CS101"
        assert report["course_name"] == "Lập trình Python"
        assert report["total_sessions"] == 15
        # Ngưỡng backend trả kèm để frontend hiển thị khớp (mặc định 15/20)
        assert report["warning_percent"] == 15
        assert report["ban_percent"] == 20

        students = {s["student_code"]: s for s in report["students"]}

        # Student 1: 3 ABSENT / 15 total sessions = 20.0% -> BANNED
        s1 = students["SV001"]
        assert s1["absent_count"] == 3
        assert s1["half_absent_count"] == 0
        assert s1["converted_absent"] == 3.0
        assert s1["rate_semester"] == 20.0
        assert s1["is_banned"] is True
        assert s1["status_label"] == "BỊ CẤM THI"

        # Student 2: 4 EXCUSED -> 0 unexcused absent -> NOT BANNED
        s2 = students["SV002"]
        assert s2["excused_count"] == 4
        assert s2["absent_count"] == 0
        assert s2["converted_absent"] == 0.0
        assert s2["rate_semester"] == 0.0
        assert s2["is_banned"] is False
        assert s2["status_label"] == "ĐỦ ĐIỀU KIỆN"

        # Student 3: 2 HALF_ABSENT + 1 PRESENT -> converted_absent = 1.0 (2 * 0.5)
        # rate_semester = 1.0 / 15 = 6.67% -> NOT BANNED
        s3 = students["SV003"]
        assert s3["half_absent_count"] == 2
        assert s3["converted_absent"] == 1.0
        assert round(s3["rate_semester"], 2) == 6.67
        assert s3["is_banned"] is False

        # 2. Teacher 2 tries to view report of Class 1 -> 403 Forbidden
        res_t2 = await ac.get(
            f"/api/v1/teacher/classes/{class1_id}/exam-ban-report",
            headers={"Authorization": f"Bearer {auth_tokens['teacher2']}"},
        )
        assert res_t2.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_teacher_export_exam_ban_excel(test_session_maker, seeded_data, auth_tokens):
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    class1_id = seeded_data["class1"].id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Teacher 1 exports exam ban excel
        res = await ac.get(
            f"/api/v1/teacher/classes/{class1_id}/export-exam-ban-excel",
            headers={"Authorization": f"Bearer {auth_tokens['teacher1']}"},
        )
        assert res.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res.headers["Content-Type"]
        assert "cam_thi_CS101.xlsx" in res.headers.get("Content-Disposition", "")

        # 2. Parse Excel file content with openpyxl
        excel_bytes = io.BytesIO(res.content)
        wb = openpyxl.load_workbook(excel_bytes)
        ws = wb.active
        assert ws is not None

        # Check header titles
        headers = [cell.value for cell in ws[4]]  # Row 4 is table header
        assert "STT" in headers
        assert "Mã Sinh Viên" in headers
        assert "Họ và Tên" in headers
        assert "Trạng Thái" in headers

        # Find rows
        rows = list(ws.iter_rows(min_row=5, values_only=False))
        assert len(rows) == 3

        # Check student 1 is marked BỊ CẤM THI
        sv001_row = next(r for r in rows if r[1].value == "SV001")
        status_cell = sv001_row[8]  # Trạng thái column
        assert status_cell.value == "BỊ CẤM THI"

        # 3. Teacher 2 cannot export class1 excel -> 403 Forbidden
        res_t2 = await ac.get(
            f"/api/v1/teacher/classes/{class1_id}/export-exam-ban-excel",
            headers={"Authorization": f"Bearer {auth_tokens['teacher2']}"},
        )
        assert res_t2.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_export_exam_ban_all_excel(test_session_maker, seeded_data, auth_tokens):
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Admin exports all school exam ban excel
        res = await ac.get(
            "/api/v1/admin/reports/export-exam-ban-all-excel",
            headers={"Authorization": f"Bearer {auth_tokens['admin']}"},
        )
        assert res.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res.headers["Content-Type"]
        assert "danh_sach_cam_thi_toan_truong.xlsx" in res.headers.get("Content-Disposition", "")

        # 2. Parse Excel
        excel_bytes = io.BytesIO(res.content)
        wb = openpyxl.load_workbook(excel_bytes)
        ws = wb.active
        assert ws is not None

        # Verify rows exist across classes (class1 has 3 enrollments, class2 has 1 enrollment -> total 4 rows)
        rows = list(ws.iter_rows(min_row=5, values_only=False))
        assert len(rows) == 4

        # 3. Teacher tries to call admin report -> 403 Forbidden
        res_teacher = await ac.get(
            "/api/v1/admin/reports/export-exam-ban-all-excel",
            headers={"Authorization": f"Bearer {auth_tokens['teacher1']}"},
        )
        assert res_teacher.status_code == 403

        # 4. Student tries to call admin report -> 403 Forbidden
        res_student = await ac.get(
            "/api/v1/admin/reports/export-exam-ban-all-excel",
            headers={"Authorization": f"Bearer {auth_tokens['student1']}"},
        )
        assert res_student.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_get_class_exam_ban_report(test_session_maker, seeded_data, auth_tokens):
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        class1_id = seeded_data["class1"].id

        # 1. Admin can view class report
        res = await ac.get(
            f"/api/v1/admin/reports/classes/{class1_id}/exam-ban-report",
            headers={"Authorization": f"Bearer {auth_tokens['admin']}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["class_id"] == class1_id
        assert len(data["students"]) == 3

        # 2. Admin can export class excel
        res_excel = await ac.get(
            f"/api/v1/admin/reports/classes/{class1_id}/export-exam-ban-excel",
            headers={"Authorization": f"Bearer {auth_tokens['admin']}"},
        )
        assert res_excel.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res_excel.headers["Content-Type"]

        # 3. Teacher gets 403 on admin report
        res_t = await ac.get(
            f"/api/v1/admin/reports/classes/{class1_id}/exam-ban-report",
            headers={"Authorization": f"Bearer {auth_tokens['teacher1']}"},
        )
        assert res_t.status_code == 403

        # 4. Student gets 403 on admin report
        res_s = await ac.get(
            f"/api/v1/admin/reports/classes/{class1_id}/exam-ban-report",
            headers={"Authorization": f"Bearer {auth_tokens['student1']}"},
        )
        assert res_s.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_teacher_student_attendance_history(test_session_maker, seeded_data, auth_tokens):
    """GV xem lịch sử điểm danh của 1 SV trong 1 môn: đủ 4 buổi + summary."""
    async def override_get_db():
        async with test_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    class1_id = seeded_data["class1"].id
    student1_id = seeded_data["student1"].id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Teacher 1 xem lịch sử student1 ở class1: 3 quá khứ ABSENT + hôm nay PRESENT
        res = await ac.get(
            f"/api/v1/teacher/classes/{class1_id}/students/{student1_id}/attendance-history",
            headers={"Authorization": f"Bearer {auth_tokens['teacher1']}"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["class_code"] == "CS101"
        assert data["student_code"] == "SV001"
        assert len(data["items"]) == 4
        assert [i["session_order"] for i in data["items"]] == [1, 2, 3, 4]
        assert data["summary"]["total_sessions"] == 4
        assert data["summary"]["absent"] == 3
        assert data["summary"]["present"] == 1

        # 2. Teacher 2 (không dạy lớp này) -> 403
        res2 = await ac.get(
            f"/api/v1/teacher/classes/{class1_id}/students/{student1_id}/attendance-history",
            headers={"Authorization": f"Bearer {auth_tokens['teacher2']}"},
        )
        assert res2.status_code == 403

        # 3. SV không thuộc lớp -> 404
        res3 = await ac.get(
            f"/api/v1/teacher/classes/{class1_id}/students/999999/attendance-history",
            headers={"Authorization": f"Bearer {auth_tokens['teacher1']}"},
        )
        assert res3.status_code == 404

    app.dependency_overrides.clear()


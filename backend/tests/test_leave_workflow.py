import io
from datetime import date, time, datetime, timezone
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from detect_ai.core.database import Base
from detect_ai.core.deps import get_db
from detect_ai.core.security import create_access_token, get_password_hash
from detect_ai.main import app
from detect_ai.models.academic import Class, ClassStudent, Schedule
from detect_ai.models.attendance_v2 import Attendance, AttendanceStatus
from detect_ai.models.leave_request import LeaveRequest, LeaveStatus
from detect_ai.models.point_ledger import PointLedger
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
async def seeded_data(test_session_maker):
    async with test_session_maker() as session:
        # Roles
        admin_role = Role(role_name="ADMIN")
        teacher_role = Role(role_name="TEACHER")
        student_role = Role(role_name="STUDENT")
        session.add_all([admin_role, teacher_role, student_role])
        await session.commit()

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
        session.add_all([teacher1, teacher2])
        await session.commit()
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
        session.add_all([student1, student2])
        await session.commit()
        await session.refresh(student1)
        await session.refresh(student2)

        sp1 = StudentProfile(user_id=student1.id, total_point=100, class_name="CNTT-K24A", major="SE")
        sp2 = StudentProfile(user_id=student2.id, total_point=100, class_name="CNTT-K24B", major="SE")
        session.add_all([sp1, sp2])

        # Classes
        class1 = Class(
            class_code="INT3306_1",
            course_name="Phát triển ứng dụng Web",
            teacher_id=teacher1.id,
            semester="HK1-2026",
            total_sessions=15,
        )
        class2 = Class(
            class_code="INT3306_2",
            course_name="Thị giác máy tính",
            teacher_id=teacher2.id,
            semester="HK1-2026",
            total_sessions=15,
        )
        session.add_all([class1, class2])
        await session.commit()
        await session.refresh(class1)
        await session.refresh(class2)

        # Enrolls: student1 in class1, student2 in class2
        session.add_all([
            ClassStudent(class_id=class1.id, student_id=student1.id),
            ClassStudent(class_id=class2.id, student_id=student2.id),
        ])

        # Schedules
        schedule1 = Schedule(
            class_id=class1.id,
            room_name="P101",
            study_date=date(2026, 9, 20),
            start_time=time(7, 30),
            end_time=time(11, 30),
            session_order=1,
        )
        schedule2 = Schedule(
            class_id=class2.id,
            room_name="P102",
            study_date=date(2026, 9, 21),
            start_time=time(13, 30),
            end_time=time(17, 30),
            session_order=1,
        )
        session.add_all([schedule1, schedule2])
        await session.commit()
        await session.refresh(schedule1)
        await session.refresh(schedule2)

        return {
            "teacher1_id": teacher1.id,
            "teacher2_id": teacher2.id,
            "student1_id": student1.id,
            "student2_id": student2.id,
            "class1_id": class1.id,
            "class2_id": class2.id,
            "schedule1_id": schedule1.id,
            "schedule2_id": schedule2.id,
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
# 1. STUDENT SUBMIT LEAVE REQUEST TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_student_submit_leave_without_proof_file(client: AsyncClient, seeded_data):
    """Sinh viên nộp đơn không kèm file minh chứng -> Thành công 200/201."""
    student_headers = make_auth_header("SV001", "STUDENT")
    data = {
        "schedule_id": str(seeded_data["schedule1_id"]),
        "reason": "Em bị sốt xuất huyết xin nghỉ học",
    }
    resp = await client.post(
        "/api/v1/student/leave-requests",
        data=data,
        headers=student_headers,
    )
    assert resp.status_code in (200, 201), resp.text
    res_data = resp.json()
    assert res_data["schedule_id"] == seeded_data["schedule1_id"]
    assert res_data["reason"] == "Em bị sốt xuất huyết xin nghỉ học"
    assert res_data["proof_image"] is None
    assert res_data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_student_submit_leave_with_valid_image(client: AsyncClient, seeded_data):
    """Sinh viên nộp đơn kèm file ảnh JPG hợp lệ -> Thành công."""
    student_headers = make_auth_header("SV001", "STUDENT")
    data = {
        "schedule_id": str(seeded_data["schedule1_id"]),
        "reason": "Có giấy khám bệnh kèm theo",
    }
    file_content = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"A" * 100
    files = {
        "proof_file": ("hospital_receipt.jpg", io.BytesIO(file_content), "image/jpeg"),
    }
    resp = await client.post(
        "/api/v1/student/leave-requests",
        data=data,
        files=files,
        headers=student_headers,
    )
    assert resp.status_code in (200, 201), resp.text
    res_data = resp.json()
    assert res_data["proof_image"] is not None
    assert "leave-proofs" in res_data["proof_image"] or ".jpg" in res_data["proof_image"]


@pytest.mark.asyncio
async def test_student_submit_leave_with_invalid_file_type(client: AsyncClient, seeded_data):
    """Sinh viên nộp file sai định dạng (.exe, .txt) -> Bị từ chối 422."""
    student_headers = make_auth_header("SV001", "STUDENT")
    data = {
        "schedule_id": str(seeded_data["schedule1_id"]),
        "reason": "Nộp file virus",
    }
    files = {
        "proof_file": ("malicious.exe", io.BytesIO(b"MZ123456"), "application/x-msdownload"),
    }
    resp = await client.post(
        "/api/v1/student/leave-requests",
        data=data,
        files=files,
        headers=student_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_student_submit_leave_with_oversized_file(client: AsyncClient, seeded_data):
    """Sinh viên nộp file > 5MB -> Bị từ chối 422."""
    student_headers = make_auth_header("SV001", "STUDENT")
    data = {
        "schedule_id": str(seeded_data["schedule1_id"]),
        "reason": "File ảnh siêu nặng",
    }
    # 5MB + 1024 bytes
    big_content = b"0" * (5 * 1024 * 1024 + 1024)
    files = {
        "proof_file": ("huge.png", io.BytesIO(big_content), "image/png"),
    }
    resp = await client.post(
        "/api/v1/student/leave-requests",
        data=data,
        files=files,
        headers=student_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_student_submit_leave_for_not_enrolled_class(client: AsyncClient, seeded_data):
    """Sinh viên nộp đơn cho lớp mình không học -> Bị từ chối 400."""
    student1_headers = make_auth_header("SV001", "STUDENT")
    # schedule2 belongs to class2 which SV001 is NOT enrolled in
    data = {
        "schedule_id": str(seeded_data["schedule2_id"]),
        "reason": "Xin nghỉ học lớp khác",
    }
    resp = await client.post(
        "/api/v1/student/leave-requests",
        data=data,
        headers=student1_headers,
    )
    assert resp.status_code == 400
    assert "lớp" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_student_cannot_submit_duplicate_leave(client: AsyncClient, seeded_data):
    """Sinh viên nộp trùng đơn cho cùng một buổi học -> Bị từ chối 400."""
    student_headers = make_auth_header("SV001", "STUDENT")
    data = {
        "schedule_id": str(seeded_data["schedule1_id"]),
        "reason": "Lý do lần 1",
    }
    r1 = await client.post("/api/v1/student/leave-requests", data=data, headers=student_headers)
    assert r1.status_code in (200, 201)

    r2 = await client.post("/api/v1/student/leave-requests", data=data, headers=student_headers)
    assert r2.status_code == 400
    assert "đã có đơn" in r2.json()["detail"].lower()


# =====================================================================
# 2. STUDENT VIEW LIST TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_student_get_leave_requests(client: AsyncClient, seeded_data):
    """Sinh viên xem danh sách các đơn nghỉ phép của mình."""
    student_headers = make_auth_header("SV001", "STUDENT")
    # Submit a request first
    await client.post(
        "/api/v1/student/leave-requests",
        data={"schedule_id": str(seeded_data["schedule1_id"]), "reason": "Em ốm"},
        headers=student_headers,
    )

    resp = await client.get("/api/v1/student/leave-requests", headers=student_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    item = items[0]
    assert item["reason"] == "Em ốm"
    assert "course_name" in item or "schedule" in item


# =====================================================================
# 3. TEACHER REVIEW TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_teacher_get_leave_requests_for_own_classes(client: AsyncClient, seeded_data):
    """Giảng viên xem danh sách đơn nghỉ phép của các lớp mình phụ trách."""
    # Student1 applies for schedule1 (Teacher1)
    sv1_headers = make_auth_header("SV001", "STUDENT")
    await client.post(
        "/api/v1/student/leave-requests",
        data={"schedule_id": str(seeded_data["schedule1_id"]), "reason": "Xin nghỉ P101"},
        headers=sv1_headers,
    )

    # Teacher1 checks
    teacher1_headers = make_auth_header("GV001", "TEACHER")
    resp1 = await client.get("/api/v1/teacher/leave-requests", headers=teacher1_headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    items1 = data1["items"] if "items" in data1 else data1
    assert len(items1) >= 1

    # Teacher2 checks (should have 0 items since class2 has no leave requests)
    teacher2_headers = make_auth_header("GV002", "TEACHER")
    resp2 = await client.get("/api/v1/teacher/leave-requests", headers=teacher2_headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    items2 = data2["items"] if "items" in data2 else data2
    assert len(items2) == 0


@pytest.mark.asyncio
async def test_teacher_forbidden_to_review_other_teacher_class(client: AsyncClient, seeded_data):
    """Giảng viên khác lớp cố tình duyệt đơn -> 403 Forbidden."""
    sv1_headers = make_auth_header("SV001", "STUDENT")
    submit_resp = await client.post(
        "/api/v1/student/leave-requests",
        data={"schedule_id": str(seeded_data["schedule1_id"]), "reason": "Nghỉ ốm"},
        headers=sv1_headers,
    )
    leave_id = submit_resp.json()["id"]

    # Teacher2 (teaches class2, not class1) tries to review
    teacher2_headers = make_auth_header("GV002", "TEACHER")
    review_resp = await client.post(
        f"/api/v1/teacher/leave-requests/{leave_id}/review",
        json={"status": "APPROVED", "feedback": "Đồng ý cho nghỉ"},
        headers=teacher2_headers,
    )
    assert review_resp.status_code == 403
    assert "quyền" in review_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_teacher_approve_updates_attendance_status(client: AsyncClient, seeded_data, test_session_maker):
    """Giảng viên duyệt APPROVED -> Bản ghi attendance chuyển thành EXCUSED."""
    sv1_headers = make_auth_header("SV001", "STUDENT")
    submit_resp = await client.post(
        "/api/v1/student/leave-requests",
        data={"schedule_id": str(seeded_data["schedule1_id"]), "reason": "Sốt cao"},
        headers=sv1_headers,
    )
    leave_id = submit_resp.json()["id"]

    # Teacher1 approves
    teacher1_headers = make_auth_header("GV001", "TEACHER")
    review_resp = await client.post(
        f"/api/v1/teacher/leave-requests/{leave_id}/review",
        json={"status": "APPROVED", "feedback": "Nghỉ ngơi giữ gìn sức khỏe"},
        headers=teacher1_headers,
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "APPROVED"

    # Check attendance table
    async with test_session_maker() as session:
        att = (
            await session.execute(
                select(Attendance).where(
                    Attendance.schedule_id == seeded_data["schedule1_id"],
                    Attendance.student_id == seeded_data["student1_id"],
                )
            )
        ).scalar_one_or_none()
        assert att is not None
        assert att.status == AttendanceStatus.EXCUSED


# =====================================================================
# 4. LATE APPROVAL REFUND LOGIC TEST
# =====================================================================

@pytest.mark.asyncio
async def test_late_approval_refund_points(client: AsyncClient, seeded_data, test_session_maker):
    """
    Kịch bản Hoàn điểm duyệt muộn:
    1. Sinh viên nộp đơn xin nghỉ (PENDING).
    2. Buổi học kết thúc và Cron 23h59 đã đánh giá vắng:
       - attendance.is_evaluated = True
       - point_ledger ghi nhận trừ 5 điểm (point_delta = -5)
       - student_profiles.total_point bị giảm xuống 95
    3. Giảng viên vào duyệt đơn sau đó (APPROVED).
    4. Hệ thống phát hiện is_evaluated == True:
       - Tạo bản ghi hoàn điểm trong point_ledger (+5 điểm, reason_code='LEAVE_REFUND')
       - Tăng lại student_profiles.total_point lên 100
       - attendance.status thành EXCUSED
    """
    sv1_headers = make_auth_header("SV001", "STUDENT")
    submit_resp = await client.post(
        "/api/v1/student/leave-requests",
        data={"schedule_id": str(seeded_data["schedule1_id"]), "reason": "Khám bệnh đột xuất"},
        headers=sv1_headers,
    )
    leave_id = submit_resp.json()["id"]

    # Giả lập Cron 23h59 đã chạy trừ điểm buổi học này
    async with test_session_maker() as session:
        # Tạo attendance đã đánh giá vắng
        att = Attendance(
            schedule_id=seeded_data["schedule1_id"],
            student_id=seeded_data["student1_id"],
            status=AttendanceStatus.ABSENT,
            is_evaluated=True,
            evaluated_at=datetime.now(timezone.utc),
        )
        session.add(att)

        # Trừ 5 điểm trong sổ cái
        deduct_ledger = PointLedger(
            student_id=seeded_data["student1_id"],
            schedule_id=seeded_data["schedule1_id"],
            point_delta=-5,
            reason_code="ABSENT",
            description="Vắng không phép buổi học",
        )
        session.add(deduct_ledger)

        # Giảm total_point của sinh viên còn 95
        sp = (
            await session.execute(
                select(StudentProfile).where(StudentProfile.user_id == seeded_data["student1_id"])
            )
        ).scalar_one()
        sp.total_point = 95
        await session.commit()

    # Giảng viên duyệt đơn muộn
    teacher1_headers = make_auth_header("GV001", "TEACHER")
    review_resp = await client.post(
        f"/api/v1/teacher/leave-requests/{leave_id}/review",
        json={"status": "APPROVED", "feedback": "Duyệt bổ sung do có giấy khám hợp lệ"},
        headers=teacher1_headers,
    )
    assert review_resp.status_code == 200

    # Kiểm tra CSDL sau khi duyệt muộn
    async with test_session_maker() as session:
        # 1. Trạng thái attendance phải là EXCUSED
        att_updated = (
            await session.execute(
                select(Attendance).where(
                    Attendance.schedule_id == seeded_data["schedule1_id"],
                    Attendance.student_id == seeded_data["student1_id"],
                )
            )
        ).scalar_one()
        assert att_updated.status == AttendanceStatus.EXCUSED

        # 2. Kiểm tra bản ghi hoàn điểm trong point_ledger
        refund_entry = (
            await session.execute(
                select(PointLedger).where(
                    PointLedger.student_id == seeded_data["student1_id"],
                    PointLedger.schedule_id == seeded_data["schedule1_id"],
                    PointLedger.reason_code == "LEAVE_REFUND",
                )
            )
        ).scalar_one_or_none()
        assert refund_entry is not None
        assert refund_entry.point_delta == 5
        assert "INT3306_1" in refund_entry.description

        # 3. Điểm của sinh viên đã được hoàn về 100
        sp_updated = (
            await session.execute(
                select(StudentProfile).where(StudentProfile.user_id == seeded_data["student1_id"])
            )
        ).scalar_one()
        assert sp_updated.total_point == 100


# =====================================================================
# 5. ADDITIONAL EDGE CASES & RBAC TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_student_submit_leave_with_valid_pdf(client: AsyncClient, seeded_data):
    """Sinh viên nộp đơn đính kèm file PDF hợp lệ."""
    student_headers = make_auth_header("SV001", "STUDENT")
    data = {
        "schedule_id": str(seeded_data["schedule1_id"]),
        "reason": "Giấy xác nhận nằm viện dạng PDF",
    }
    pdf_content = b"%PDF-1.4 " + b"Sample PDF content"
    files = {
        "proof_file": ("certificate.pdf", io.BytesIO(pdf_content), "application/pdf"),
    }
    resp = await client.post(
        "/api/v1/student/leave-requests",
        data=data,
        files=files,
        headers=student_headers,
    )
    assert resp.status_code in (200, 201), resp.text
    res_data = resp.json()
    assert res_data["proof_image"] is not None
    assert ".pdf" in res_data["proof_image"]


@pytest.mark.asyncio
async def test_teacher_reject_leave_request(client: AsyncClient, seeded_data):
    """Giảng viên từ chối đơn nghỉ phép (REJECTED)."""
    sv1_headers = make_auth_header("SV001", "STUDENT")
    submit_resp = await client.post(
        "/api/v1/student/leave-requests",
        data={"schedule_id": str(seeded_data["schedule1_id"]), "reason": "Lý do không chính đáng"},
        headers=sv1_headers,
    )
    leave_id = submit_resp.json()["id"]

    teacher1_headers = make_auth_header("GV001", "TEACHER")
    review_resp = await client.post(
        f"/api/v1/teacher/leave-requests/{leave_id}/review",
        json={"status": "REJECTED", "feedback": "Không chấp nhận lý do này"},
        headers=teacher1_headers,
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "REJECTED"
    assert review_resp.json()["teacher_feedback"] == "Không chấp nhận lý do này"


@pytest.mark.asyncio
async def test_teacher_filter_by_status(client: AsyncClient, seeded_data):
    """Giảng viên lọc danh sách đơn theo trạng thái (PENDING, APPROVED)."""
    sv1_headers = make_auth_header("SV001", "STUDENT")
    submit_resp = await client.post(
        "/api/v1/student/leave-requests",
        data={"schedule_id": str(seeded_data["schedule1_id"]), "reason": "Xin nghỉ chờ duyệt"},
        headers=sv1_headers,
    )
    leave_id = submit_resp.json()["id"]

    teacher1_headers = make_auth_header("GV001", "TEACHER")
    # Lọc PENDING
    pending_resp = await client.get("/api/v1/teacher/leave-requests?status=PENDING", headers=teacher1_headers)
    assert pending_resp.status_code == 200
    pending_items = pending_resp.json()["items"]
    assert any(item["id"] == leave_id for item in pending_items)

    # Lọc APPROVED (chưa có)
    approved_resp = await client.get("/api/v1/teacher/leave-requests?status=APPROVED", headers=teacher1_headers)
    assert approved_resp.status_code == 200
    approved_items = approved_resp.json()["items"]
    assert not any(item["id"] == leave_id for item in approved_items)


@pytest.mark.asyncio
async def test_teacher_review_non_existent_leave_request(client: AsyncClient, seeded_data):
    """Giảng viên duyệt đơn không tồn tại -> 404."""
    teacher1_headers = make_auth_header("GV001", "TEACHER")
    resp = await client.post(
        "/api/v1/teacher/leave-requests/99999/review",
        json={"status": "APPROVED", "feedback": "Ok"},
        headers=teacher1_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_student_submit_non_existent_schedule(client: AsyncClient, seeded_data):
    """Sinh viên nộp đơn cho schedule không tồn tại -> 404."""
    student_headers = make_auth_header("SV001", "STUDENT")
    resp = await client.post(
        "/api/v1/student/leave-requests",
        data={"schedule_id": "99999", "reason": "Lịch ảo"},
        headers=student_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_leave_requests_rbac_isolation(client: AsyncClient, seeded_data):
    """Kiểm tra cách ly phân quyền giữa STUDENT và TEACHER."""
    student_headers = make_auth_header("SV001", "STUDENT")
    teacher_headers = make_auth_header("GV001", "TEACHER")

    # Sinh viên cố gọi API giảng viên -> 403
    r1 = await client.get("/api/v1/teacher/leave-requests", headers=student_headers)
    assert r1.status_code == 403

    # Giảng viên cố nộp đơn sinh viên -> 403
    r2 = await client.post(
        "/api/v1/student/leave-requests",
        data={"schedule_id": str(seeded_data["schedule1_id"]), "reason": "GV nộp đơn"},
        headers=teacher_headers,
    )
    assert r2.status_code == 403


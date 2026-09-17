"""Task 13 — Bộ kiểm thử E2E (End-to-End) cho Hệ thống Quản lý Lớp học Thông minh.

Kiểm thử tích hợp xuyên suốt 5 kịch bản nghiệp vụ theo kế hoạch:
    1. Sinh viên đi học đúng giờ, check-in/check-out, có đồng phục -> Cron 23h59 cộng 2 điểm.
    2. Sinh viên quên check-out -> Cron 23h59 đánh vắng nửa buổi, trừ 2 điểm.
    3. Sinh viên vắng có đơn nghỉ phép kèm minh chứng được duyệt TRƯỚC khi Cron chạy
       -> EXCUSED, không trừ điểm.
    4. Đơn nghỉ phép được duyệt SAU khi Cron đã trừ điểm -> hệ thống tự động hoàn điểm
       (point_ledger reason_code = LEAVE_REFUND).
    5. Sinh viên vắng quá 20% số buổi -> xuất hiện trong danh sách cấm thi (API + file Excel
       của Giảng viên và file Excel toàn trường của Admin).

Khác với các test đơn lẻ (Task 4-7), bộ test này đi qua đúng các HTTP endpoint thật
(Kiosk API -> Cron API -> Student Portal API -> Teacher Review API -> Report API)
trên cùng một cơ sở dữ liệu, mô phỏng trọn vẹn một ngày vận hành của nhà trường.
"""

from __future__ import annotations

import io
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from detect_ai.core.database import Base
from detect_ai.core.deps import get_db
from detect_ai.core.security import create_access_token, get_password_hash
from detect_ai.main import app
from detect_ai.models.academic import Class, ClassStudent, Schedule
from detect_ai.models.attendance_v2 import Attendance, AttendanceStatus
from detect_ai.models.leave_request import LeaveRequest, LeaveStatus
from detect_ai.models.point_ledger import PointLedger
from detect_ai.models.system_setting import SystemSetting
from detect_ai.models.user import Role, StudentProfile, TeacherProfile, User

# =====================================================================
# HẰNG SỐ DÙNG CHUNG
# =====================================================================
KIOSK_API_KEY = "kiosk-secret-key-2026"
KIOSK_HEADERS = {"X-Kiosk-Api-Key": KIOSK_API_KEY}

STUDENT_1 = "SV001"
STUDENT_2 = "SV002"
STUDENT_3 = "SV003"
STUDENT_4 = "SV004"
STUDENT_5 = "SV005"
STUDENT_6 = "SV006"

TEACHER_1 = "GV001"
TEACHER_2 = "GV002"
ADMIN_CODE = "ADMIN01"

TODAY = date.today()

# Phòng học cho từng kịch bản (mỗi kịch bản 1 phòng riêng để không xung đột lịch)
ROOM_SC1 = "E2E-A101"  # 08:00 - 10:00
ROOM_SC2 = "E2E-A102"  # 13:00 - 15:00
ROOM_SC3 = "E2E-A103"  # 15:30 - 17:30
ROOM_SC4 = "E2E-A104"  # 18:00 - 20:00
ROOM_CLASS2 = "E2E-B201"  # 09:00 - 11:00 (lớp của giảng viên khác)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"e2e-proof-content" * 4
INITIAL_POINT = 100


# =====================================================================
# FIXTURES
# =====================================================================
@pytest_asyncio.fixture
async def test_session_maker():
    """CSDL SQLite in-memory với toàn bộ schema của hệ thống."""
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
    """Dữ liệu nền: 1 Admin, 2 Giảng viên, 6 Sinh viên, 2 lớp học phần, 5 buổi học trong ngày."""
    async with test_session_maker() as session:
        roles = {"ADMIN": Role(role_name="ADMIN"), "TEACHER": Role(role_name="TEACHER"), "STUDENT": Role(role_name="STUDENT")}
        session.add_all(list(roles.values()))
        await session.commit()

        admin = User(
            user_code=ADMIN_CODE,
            full_name="Quản trị viên E2E",
            email="admin.e2e@school.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=roles["ADMIN"].id,
            is_active=True,
        )
        teacher1 = User(
            user_code=TEACHER_1,
            full_name="Giảng viên E2E 1",
            email="gv1.e2e@school.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=roles["TEACHER"].id,
            is_active=True,
        )
        teacher2 = User(
            user_code=TEACHER_2,
            full_name="Giảng viên E2E 2",
            email="gv2.e2e@school.edu.vn",
            password_hash=get_password_hash("Pass@123"),
            role_id=roles["TEACHER"].id,
            is_active=True,
        )
        students = [
            User(
                user_code=f"SV00{i}",
                full_name=f"Sinh viên E2E {i}",
                email=f"sv{i}.e2e@student.edu.vn",
                password_hash=get_password_hash("Pass@123"),
                role_id=roles["STUDENT"].id,
                is_active=True,
            )
            for i in range(1, 7)
        ]
        session.add_all([admin, teacher1, teacher2, *students])
        await session.commit()

        session.add_all(
            [
                TeacherProfile(user_id=teacher1.id, department="CNTT", academic_title="ThS", office_room="A1-101"),
                TeacherProfile(user_id=teacher2.id, department="CNTT", academic_title="TS", office_room="A1-102"),
            ]
            + [
                StudentProfile(user_id=sv.id, face_embedding="[0.11, 0.22]", total_point=INITIAL_POINT, class_name="CNTT-K24E2E", major="KTPM")
                for sv in students
            ]
        )

        class1 = Class(
            class_code="E2E_INT3306_1",
            course_name="Phát triển ứng dụng Web (E2E)",
            teacher_id=teacher1.id,
            semester="HK1-2026",
            total_sessions=12,
        )
        class2 = Class(
            class_code="E2E_INT3306_2",
            course_name="Thị giác máy tính (E2E)",
            teacher_id=teacher2.id,
            semester="HK1-2026",
            total_sessions=10,
        )
        session.add_all([class1, class2])
        await session.commit()

        # Sinh viên 1..6 học lớp 1; sinh viên 5 học thêm lớp 2 (lớp của giảng viên khác)
        session.add_all(
            [ClassStudent(class_id=class1.id, student_id=sv.id) for sv in students]
            + [ClassStudent(class_id=class2.id, student_id=students[4].id)]
        )

        # Mỗi kịch bản diễn ra trong một ngày khác nhau để việc đánh giá 23h59 của ngày nào
        # chỉ tác động tới đúng buổi học của ngày đó (cô lập kịch bản như vận hành thật).
        day1 = TODAY - timedelta(days=3)
        day2 = TODAY - timedelta(days=2)
        day3 = TODAY - timedelta(days=1)
        day4 = TODAY

        sc1 = Schedule(class_id=class1.id, room_name=ROOM_SC1, study_date=day1, start_time=time(8, 0), end_time=time(10, 0), session_order=1)
        sc2 = Schedule(class_id=class1.id, room_name=ROOM_SC2, study_date=day2, start_time=time(13, 0), end_time=time(15, 0), session_order=2)
        sc3 = Schedule(class_id=class1.id, room_name=ROOM_SC3, study_date=day3, start_time=time(15, 30), end_time=time(17, 30), session_order=3)
        sc4 = Schedule(class_id=class1.id, room_name=ROOM_SC4, study_date=day4, start_time=time(18, 0), end_time=time(20, 0), session_order=4)
        sc5 = Schedule(class_id=class2.id, room_name=ROOM_CLASS2, study_date=day4, start_time=time(9, 0), end_time=time(11, 0), session_order=1)
        session.add_all([sc1, sc2, sc3, sc4, sc5])

        session.add_all(
            [
                SystemSetting(key="POINT_FULL_ATTENDANCE", value="2"),
                SystemSetting(key="POINT_LATE", value="-1"),
                SystemSetting(key="POINT_HALF_ABSENCE", value="-2"),
                SystemSetting(key="POINT_ABSENCE_WITHOUT_LEAVE", value="-5"),
                SystemSetting(key="POINT_UNIFORM_VIOLATION", value="-2"),
                SystemSetting(key="LATE_TOLERANCE_MINUTES", value="15"),
                SystemSetting(key="REQUIRE_CHECKOUT", value="true"),
                SystemSetting(key="MAX_ABSENCE_PERCENT_EXAM_BAN", value="20"),
            ]
        )
        await session.commit()

        return {
            "today": TODAY,
            "day1": day1,
            "day2": day2,
            "day3": day3,
            "day4": day4,
            "admin_id": admin.id,
            "teacher1_id": teacher1.id,
            "teacher2_id": teacher2.id,
            "student_ids": [sv.id for sv in students],
            "student_id_by_code": {sv.user_code: sv.id for sv in students},
            "class1_id": class1.id,
            "class2_id": class2.id,
            "sc1": sc1.id,
            "sc2": sc2.id,
            "sc3": sc3.id,
            "sc4": sc4.id,
            "class2_schedule_id": sc5.id,
            "schedule_ids": [sc1.id, sc2.id, sc3.id, sc4.id],
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


# =====================================================================
# HELPERS
# =====================================================================
def auth_headers(user_code: str, role: str) -> Dict[str, str]:
    token = create_access_token(data={"sub": user_code, "role": role})
    return {"Authorization": f"Bearer {token}"}


def moment_at(hour: int, minute: int = 0, day: date = TODAY) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)


async def kiosk_scan(
    client: AsyncClient,
    *,
    room: str,
    student_code: str,
    moment: datetime,
    has_uniform: bool = True,
    api_key: str = KIOSK_API_KEY,
):
    headers = {"X-Kiosk-Api-Key": api_key} if api_key else {}
    return await client.post(
        "/api/v1/attendance/kiosk-record",
        json={
            "room_name": room,
            "student_code": student_code,
            "has_uniform": has_uniform,
            "timestamp": moment.isoformat(),
        },
        headers=headers,
    )


async def run_evaluation_now(client: AsyncClient, target_date: date = TODAY) -> Dict[str, Any]:
    """Admin kích hoạt chạy bù Cron đánh giá 23h59."""
    resp = await client.post(
        f"/api/v1/admin/evaluation/run-now?target_date={target_date.isoformat()}",
        headers=auth_headers(ADMIN_CODE, "ADMIN"),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def submit_leave(
    client: AsyncClient,
    student_code: str,
    *,
    schedule_id: int,
    reason: str = "Sinh viên bị ốm, có giấy khám bệnh của bệnh viện.",
    filename: str = "giay_kham_benh.png",
    content: bytes = PNG_BYTES,
    content_type: str = "image/png",
):
    files = {"proof_file": (filename, io.BytesIO(content), content_type)} if filename else None
    return await client.post(
        "/api/v1/student/leave-requests",
        data={"schedule_id": str(schedule_id), "reason": reason},
        files=files,
        headers=auth_headers(student_code, "STUDENT"),
    )


async def review_leave(
    client: AsyncClient,
    *,
    teacher_code: str,
    leave_id: int,
    status: str = "APPROVED",
    feedback: str = "Đã kiểm tra minh chứng, đồng ý cho nghỉ.",
):
    return await client.post(
        f"/api/v1/teacher/leave-requests/{leave_id}/review",
        json={"status": status, "feedback": feedback},
        headers=auth_headers(teacher_code, "TEACHER"),
    )


async def fetch_attendance(session_maker, schedule_id: int, student_id: int):
    async with session_maker() as session:
        return (
            await session.execute(
                select(Attendance).where(
                    Attendance.schedule_id == schedule_id,
                    Attendance.student_id == student_id,
                )
            )
        ).scalar_one_or_none()


async def fetch_total_point(session_maker, student_id: int) -> int:
    async with session_maker() as session:
        profile = (
            await session.execute(select(StudentProfile).where(StudentProfile.user_id == student_id))
        ).scalar_one_or_none()
        assert profile is not None, "Không tìm thấy student_profiles của sinh viên"
        return profile.total_point


async def fetch_ledger(session_maker, student_id: int, schedule_id: int | None = None) -> List[PointLedger]:
    async with session_maker() as session:
        stmt = select(PointLedger).where(PointLedger.student_id == student_id)
        if schedule_id is not None:
            stmt = stmt.where(PointLedger.schedule_id == schedule_id)
        return list((await session.execute(stmt)).scalars().all())


def sheet_rows(content: bytes) -> List[List[str]]:
    wb = load_workbook(io.BytesIO(content))
    ws = wb.active
    return [[("" if c.value is None else str(c.value)) for c in row] for row in ws.iter_rows()]


def find_excel_row(content: bytes, student_code: str) -> List[str]:
    for row in sheet_rows(content):
        if len(row) > 1 and row[1].strip() == student_code:
            return row
    raise AssertionError(f"Không tìm thấy dòng của sinh viên {student_code} trong file Excel")


def find_by_schedule(items: List[dict], schedule_id: int) -> dict:
    for item in items:
        if item.get("schedule_id") == schedule_id:
            return item
    raise AssertionError(f"Không tìm thấy bản ghi của buổi học {schedule_id}")


# =====================================================================
# KỊCH BẢN 1: Đi học đúng giờ + có đồng phục -> +2 điểm
# =====================================================================
@pytest.mark.asyncio
async def test_scenario_1_on_time_with_uniform_gets_full_point(client, test_session_maker, seeded_data):
    sc1 = seeded_data["sc1"]
    day1 = seeded_data["day1"]
    sv1 = seeded_data["student_id_by_code"][STUDENT_1]

    # 1. Quét Kiosk check-in lúc 08:05 (trong ngưỡng trễ 15 phút) và có đồng phục
    resp_in = await kiosk_scan(client, room=ROOM_SC1, student_code=STUDENT_1, moment=moment_at(8, 5, day1), has_uniform=True)
    assert resp_in.status_code == 200, resp_in.text
    data_in = resp_in.json()
    assert data_in["type"] == "CHECK_IN"
    assert data_in["status"] == "PRESENT"
    assert data_in["has_uniform"] is True
    assert data_in["student_code"] == STUDENT_1

    # 2. Quét Kiosk check-out lúc 10:00
    resp_out = await kiosk_scan(client, room=ROOM_SC1, student_code=STUDENT_1, moment=moment_at(10, 0, day1), has_uniform=True)
    assert resp_out.status_code == 200, resp_out.text
    data_out = resp_out.json()
    assert data_out["type"] == "CHECK_OUT"
    assert data_out["has_uniform"] is True

    # 3. Cron 23h59 (chạy bù thủ công qua API Admin)
    stats = await run_evaluation_now(client, day1)
    assert stats["target_date"] == day1.isoformat()
    assert stats["total_records"] >= 1

    # 4. Bản ghi điểm danh: PRESENT, đã đánh giá
    att = await fetch_attendance(test_session_maker, sc1, sv1)
    assert att.status == AttendanceStatus.PRESENT
    assert att.is_evaluated is True
    assert att.evaluated_at is not None
    assert att.check_in_time is not None and att.check_out_time is not None

    # 5. Sổ cái điểm: +2 điểm NIGHTLY_EVAL
    ledger = await fetch_ledger(test_session_maker, sv1, sc1)
    assert len(ledger) == 1
    assert ledger[0].point_delta == 2
    assert ledger[0].reason_code == "NIGHTLY_EVAL"
    assert await fetch_total_point(test_session_maker, sv1) == INITIAL_POINT + 2

    # 6. Portal sinh viên phản ánh đúng kết quả
    resp_att = await client.get("/api/v1/student/attendance", headers=auth_headers(STUDENT_1, "STUDENT"))
    assert resp_att.status_code == 200
    item = find_by_schedule(resp_att.json(), sc1)
    assert item["status"] == "PRESENT"
    assert item["has_uniform"] is True

    resp_ledger = await client.get("/api/v1/student/conduct-ledger", headers=auth_headers(STUDENT_1, "STUDENT"))
    assert resp_ledger.status_code == 200
    ledger_body = resp_ledger.json()
    assert ledger_body["total_point"] == INITIAL_POINT + 2
    assert any(e["reason_code"] == "NIGHTLY_EVAL" and e["point_delta"] == 2 for e in ledger_body["items"])


# =====================================================================
# KỊCH BẢN 2: Quên check-out -> vắng nửa buổi, -2 điểm
# =====================================================================
@pytest.mark.asyncio
async def test_scenario_2_missing_checkout_is_half_absent(client, test_session_maker, seeded_data):
    sc2 = seeded_data["sc2"]
    day2 = seeded_data["day2"]
    sv2 = seeded_data["student_id_by_code"][STUDENT_2]

    # 1. Chỉ quét check-in lúc 13:05, không quét check-out
    resp_in = await kiosk_scan(client, room=ROOM_SC2, student_code=STUDENT_2, moment=moment_at(13, 5, day2), has_uniform=True)
    assert resp_in.status_code == 200, resp_in.text
    assert resp_in.json()["type"] == "CHECK_IN"

    # 2. Cron 23h59 đánh giá
    await run_evaluation_now(client, day2)

    att = await fetch_attendance(test_session_maker, sc2, sv2)
    assert att.status == AttendanceStatus.HALF_ABSENT
    assert att.check_out_time is None
    assert att.is_evaluated is True

    ledger = await fetch_ledger(test_session_maker, sv2, sc2)
    assert len(ledger) == 1
    assert ledger[0].point_delta == -2
    assert await fetch_total_point(test_session_maker, sv2) == INITIAL_POINT - 2

    resp_att = await client.get("/api/v1/student/attendance", headers=auth_headers(STUDENT_2, "STUDENT"))
    assert find_by_schedule(resp_att.json(), sc2)["status"] == "HALF_ABSENT"


# =====================================================================
# KỊCH BẢN 3: Nghỉ có phép (duyệt trước 23h59) -> EXCUSED, không trừ điểm
# =====================================================================
@pytest.mark.asyncio
async def test_scenario_3_approved_leave_before_evaluation_is_excused(client, test_session_maker, seeded_data):
    sc3 = seeded_data["sc3"]
    day3 = seeded_data["day3"]
    sv3 = seeded_data["student_id_by_code"][STUDENT_3]

    # 1. Sinh viên vắng, nộp đơn kèm ảnh giấy khám bệnh
    resp_submit = await submit_leave(client, STUDENT_3, schedule_id=sc3, reason="Sốt xuất huyết, có giấy khám bệnh.")
    assert resp_submit.status_code == 201, resp_submit.text
    leave = resp_submit.json()
    assert leave["status"] == "PENDING"
    assert leave["proof_image"]
    assert leave["class_code"] == "E2E_INT3306_1"

    # 2. Giảng viên phụ trách thấy đơn trong hàng chờ duyệt
    resp_pending = await client.get("/api/v1/teacher/leave-requests?status=PENDING", headers=auth_headers(TEACHER_1, "TEACHER"))
    assert resp_pending.status_code == 200
    assert any(item["id"] == leave["id"] for item in resp_pending.json()["items"])

    # 3. Giảng viên duyệt đơn
    resp_review = await review_leave(client, teacher_code=TEACHER_1, leave_id=leave["id"], status="APPROVED")
    assert resp_review.status_code == 200, resp_review.text
    assert resp_review.json()["status"] == "APPROVED"

    # 4. Cron 23h59 chạy sau đó -> EXCUSED, không trừ điểm
    await run_evaluation_now(client, day3)

    att = await fetch_attendance(test_session_maker, sc3, sv3)
    assert att.status == AttendanceStatus.EXCUSED
    assert att.is_evaluated is True

    ledger = await fetch_ledger(test_session_maker, sv3, sc3)
    assert len(ledger) == 1
    assert ledger[0].point_delta == 0
    assert ledger[0].reason_code == "NIGHTLY_EVAL"
    assert await fetch_total_point(test_session_maker, sv3) == INITIAL_POINT

    # 5. Portal sinh viên: nghỉ có phép, tổng điểm không đổi
    resp_att = await client.get("/api/v1/student/attendance", headers=auth_headers(STUDENT_3, "STUDENT"))
    assert find_by_schedule(resp_att.json(), sc3)["status"] == "EXCUSED"
    resp_ledger = await client.get("/api/v1/student/conduct-ledger", headers=auth_headers(STUDENT_3, "STUDENT"))
    assert resp_ledger.json()["total_point"] == INITIAL_POINT


# =====================================================================
# KỊCH BẢN 4: Duyệt đơn muộn sau 23h59 -> hoàn điểm tự động
# =====================================================================
@pytest.mark.asyncio
async def test_scenario_4_late_approval_refunds_points(client, test_session_maker, seeded_data):
    sc4 = seeded_data["sc4"]
    day4 = seeded_data["day4"]
    sv4 = seeded_data["student_id_by_code"][STUDENT_4]

    # 1. Sinh viên vắng không quét -> Cron 23h59 đánh ABSENT và trừ 5 điểm
    await run_evaluation_now(client, day4)
    att = await fetch_attendance(test_session_maker, sc4, sv4)
    assert att.status == AttendanceStatus.ABSENT
    assert att.is_evaluated is True

    ledger_after_eval = await fetch_ledger(test_session_maker, sv4, sc4)
    assert [e.point_delta for e in ledger_after_eval] == [-5]
    assert await fetch_total_point(test_session_maker, sv4) == INITIAL_POINT - 5

    # 2. Hôm sau sinh viên mới nộp đơn xin phép (duyệt muộn)
    resp_submit = await submit_leave(client, STUDENT_4, schedule_id=sc4, reason="Nhập viện đột xuất, bổ sung giấy tờ sau.")
    assert resp_submit.status_code == 201, resp_submit.text
    leave_id = resp_submit.json()["id"]

    # 3. Giảng viên duyệt đơn -> hệ thống hoàn điểm
    resp_review = await review_leave(client, teacher_code=TEACHER_1, leave_id=leave_id, status="APPROVED")
    assert resp_review.status_code == 200, resp_review.text
    assert resp_review.json()["status"] == "APPROVED"

    # 4. Điểm được hoàn qua sổ cái LEAVE_REFUND, trạng thái buổi học thành EXCUSED
    ledger_after_refund = await fetch_ledger(test_session_maker, sv4, sc4)
    deltas = sorted(e.point_delta for e in ledger_after_refund)
    assert deltas == [-5, 5]
    refund = next(e for e in ledger_after_refund if e.reason_code == "LEAVE_REFUND")
    assert refund.point_delta == 5
    assert await fetch_total_point(test_session_maker, sv4) == INITIAL_POINT

    att_after = await fetch_attendance(test_session_maker, sc4, sv4)
    assert att_after.status == AttendanceStatus.EXCUSED

    # 5. Sổ cái điện tử của sinh viên phản ánh cả giao dịch trừ và hoàn điểm
    resp_ledger = await client.get("/api/v1/student/conduct-ledger", headers=auth_headers(STUDENT_4, "STUDENT"))
    assert resp_ledger.status_code == 200
    body = resp_ledger.json()
    assert body["total_point"] == INITIAL_POINT
    codes = [e["reason_code"] for e in body["items"]]
    assert "NIGHTLY_EVAL" in codes and "LEAVE_REFUND" in codes


# =====================================================================
# KỊCH BẢN 5: Vắng quá 20% -> cấm thi + xuất file Excel
# =====================================================================
@pytest.mark.asyncio
async def test_scenario_5_absence_over_threshold_is_exam_banned_and_exported(client, test_session_maker, seeded_data):
    class1 = seeded_data["class1_id"]
    schedule_ids = seeded_data["schedule_ids"]
    sv6 = seeded_data["student_id_by_code"][STUDENT_6]

    # 0. Chuẩn bị: 5 sinh viên đầu đi học đầy đủ 4/4 buổi; SV006 chỉ có mặt buổi thứ 4
    #    => SV006 vắng 3/4 buổi đã diễn ra, tương đương 3/12 buổi của cả kỳ = 25% >= 20%.
    async with test_session_maker() as session:
        for student_id in seeded_data["student_ids"][:5]:
            for schedule_id in schedule_ids:
                session.add(
                    Attendance(
                        schedule_id=schedule_id,
                        student_id=student_id,
                        check_in_time=moment_at(8, 0),
                        check_out_time=moment_at(10, 0),
                        has_uniform=True,
                        status=AttendanceStatus.PRESENT,
                        is_evaluated=True,
                    )
                )
        session.add(
            Attendance(
                schedule_id=seeded_data["sc4"],
                student_id=sv6,
                check_in_time=moment_at(18, 0),
                check_out_time=moment_at(20, 0),
                has_uniform=True,
                status=AttendanceStatus.PRESENT,
                is_evaluated=True,
            )
        )
        await session.commit()

    # 1. Báo cáo cấm thi của giảng viên phụ trách lớp
    resp_report = await client.get(f"/api/v1/teacher/classes/{class1}/exam-ban-report", headers=auth_headers(TEACHER_1, "TEACHER"))
    assert resp_report.status_code == 200, resp_report.text
    report = resp_report.json()
    assert report["class_code"] == "E2E_INT3306_1"
    assert report["elapsed_sessions"] == len(schedule_ids)

    row = next(r for r in report["students"] if r["student_code"] == STUDENT_6)
    assert row["absent_count"] == 3
    assert row["rate_semester"] == 25.0
    assert row["is_banned"] is True
    assert row["status_label"] == "BỊ CẤM THI"

    # Các sinh viên đi học đầy đủ không bị cấm thi
    good = next(r for r in report["students"] if r["student_code"] == STUDENT_1)
    assert good["absent_count"] == 0
    assert good["is_banned"] is False

    # 2. Xuất file Excel cấm thi của lớp (giảng viên)
    resp_excel = await client.get(
        f"/api/v1/teacher/classes/{class1}/export-exam-ban-excel",
        headers=auth_headers(TEACHER_1, "TEACHER"),
    )
    assert resp_excel.status_code == 200, resp_excel.text
    assert resp_excel.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    excel_row = find_excel_row(resp_excel.content, STUDENT_6)
    assert excel_row[5] == "3"  # Số buổi vắng
    assert excel_row[7] == "25.0%"  # Tỷ lệ vắng cả kỳ
    assert excel_row[8] == "BỊ CẤM THI"
    assert "DANH SÁCH CẤM THI LỚP E2E_INT3306_1" in sheet_rows(resp_excel.content)[0][0]

    # 3. Admin xuất file Excel cấm thi toàn trường
    resp_all = await client.get("/api/v1/admin/reports/export-exam-ban-all-excel", headers=auth_headers(ADMIN_CODE, "ADMIN"))
    assert resp_all.status_code == 200, resp_all.text
    all_rows = sheet_rows(resp_all.content)
    assert "DANH SÁCH CẤM THI TOÀN TRƯỜNG" in all_rows[0][0]
    assert find_excel_row(resp_all.content, STUDENT_6)[8] == "BỊ CẤM THI"

    # 4. Giảng viên khác không được xem/xuất báo cáo của lớp mình không phụ trách
    resp_forbidden = await client.get(
        f"/api/v1/teacher/classes/{class1}/exam-ban-report", headers=auth_headers(TEACHER_2, "TEACHER")
    )
    assert resp_forbidden.status_code == 403
    resp_forbidden_excel = await client.get(
        f"/api/v1/teacher/classes/{class1}/export-exam-ban-excel", headers=auth_headers(TEACHER_2, "TEACHER")
    )
    assert resp_forbidden_excel.status_code == 403


# =====================================================================
# BẢO MẬT & RBAC XUYÊN SUỐT
# =====================================================================
@pytest.mark.asyncio
async def test_security_kiosk_key_and_rbac_matrix(client, test_session_maker, seeded_data):
    sc1 = seeded_data["sc1"]
    day1 = seeded_data["day1"]

    # 1. Kiosk API bắt buộc X-Kiosk-Api-Key
    resp_no_key = await kiosk_scan(client, room=ROOM_SC1, student_code=STUDENT_1, moment=moment_at(8, 5, day1), api_key="")
    assert resp_no_key.status_code == 401
    resp_bad_key = await kiosk_scan(client, room=ROOM_SC1, student_code=STUDENT_1, moment=moment_at(8, 5, day1), api_key="sai-key")
    assert resp_bad_key.status_code == 401

    # 2. Kiosk quét ngoài giờ học / sai phòng -> không tìm thấy ca học
    resp_wrong_room = await kiosk_scan(client, room="E2E-KHONG-CO-PHONG", student_code=STUDENT_1, moment=moment_at(8, 5, day1))
    assert resp_wrong_room.status_code == 404
    resp_out_of_window = await kiosk_scan(client, room=ROOM_SC1, student_code=STUDENT_1, moment=moment_at(23, 30, day1))
    assert resp_out_of_window.status_code == 404

    # 3. Kiosk quét mã sinh viên không tồn tại
    resp_unknown = await kiosk_scan(client, room=ROOM_SC1, student_code="SV_KHONG_TON_TAI", moment=moment_at(8, 5, day1))
    assert resp_unknown.status_code == 404

    # 4. Cron đánh giá chỉ dành cho Admin
    resp_no_auth = await client.post(f"/api/v1/admin/evaluation/run-now?target_date={TODAY.isoformat()}")
    assert resp_no_auth.status_code == 401
    for code, role in ((STUDENT_1, "STUDENT"), (TEACHER_1, "TEACHER")):
        resp_forbidden = await client.post(
            f"/api/v1/admin/evaluation/run-now?target_date={TODAY.isoformat()}",
            headers=auth_headers(code, role),
        )
        assert resp_forbidden.status_code == 403

    # 5. Portal sinh viên yêu cầu đăng nhập và đúng vai trò
    resp_anon = await client.get("/api/v1/student/conduct-ledger")
    assert resp_anon.status_code == 401
    resp_teacher = await client.get("/api/v1/student/conduct-ledger", headers=auth_headers(TEACHER_1, "TEACHER"))
    assert resp_teacher.status_code == 403

    # 6. Sinh viên không thể nộp đơn cho lớp mình không học
    resp_wrong_class = await submit_leave(client, STUDENT_2, schedule_id=seeded_data["class2_schedule_id"])
    assert resp_wrong_class.status_code == 400

    # 7. Minh chứng sai định dạng bị từ chối (chỉ nhận jpeg/png/pdf <= 5MB)
    resp_bad_mime = await submit_leave(
        client, STUDENT_1, schedule_id=sc1, filename="virus.exe", content=b"MZ", content_type="application/x-msdownload"
    )
    assert resp_bad_mime.status_code == 422

    # 8. Không cho nộp trùng đơn nghỉ phép cho cùng một buổi học
    first = await submit_leave(client, STUDENT_1, schedule_id=sc1)
    assert first.status_code == 201
    second = await submit_leave(client, STUDENT_1, schedule_id=sc1)
    assert second.status_code == 400

    # 9. Giảng viên không được duyệt đơn của lớp mình không phụ trách
    sv5 = seeded_data["student_id_by_code"][STUDENT_5]
    async with test_session_maker() as session:
        foreign_leave = LeaveRequest(
            schedule_id=seeded_data["class2_schedule_id"],
            student_id=sv5,
            reason="Đơn của lớp do giảng viên khác phụ trách",
            status=LeaveStatus.PENDING,
        )
        session.add(foreign_leave)
        await session.commit()
        foreign_leave_id = foreign_leave.id

    resp_foreign_review = await review_leave(
        client, teacher_code=TEACHER_1, leave_id=foreign_leave_id, status="APPROVED"
    )
    assert resp_foreign_review.status_code == 403


# =====================================================================
# TÍNH IDEMPOTENT & CÂN ĐỐI SỔ CÁI
# =====================================================================
@pytest.mark.asyncio
async def test_ledger_reconciliation_and_cron_idempotency(client, test_session_maker, seeded_data):
    sv1 = seeded_data["student_id_by_code"][STUDENT_1]
    day1 = seeded_data["day1"]

    # 1. Một ngày vận hành: SV001 đi học đầy đủ, các bạn khác vắng
    await kiosk_scan(client, room=ROOM_SC1, student_code=STUDENT_1, moment=moment_at(8, 5, day1), has_uniform=True)
    await kiosk_scan(client, room=ROOM_SC1, student_code=STUDENT_1, moment=moment_at(10, 0, day1), has_uniform=True)

    first_run = await run_evaluation_now(client, day1)
    assert first_run["schedules_evaluated"] == 1
    assert first_run["total_records"] == len(seeded_data["student_ids"])

    # 2. Chạy lại Cron cho cùng ngày -> không sinh thêm bản ghi, không trừ điểm lặp
    ledger_before = await fetch_ledger(test_session_maker, sv1)
    point_before = await fetch_total_point(test_session_maker, sv1)

    second_run = await run_evaluation_now(client, day1)
    assert second_run["total_records"] == 0
    assert second_run["students_evaluated"] == 0

    assert len(await fetch_ledger(test_session_maker, sv1)) == len(ledger_before)
    assert await fetch_total_point(test_session_maker, sv1) == point_before

    # 3. Bất biến sổ cái: tổng point_delta trong point_ledger == total_point - 100 (điểm gốc)
    for student_id in seeded_data["student_ids"]:
        entries = await fetch_ledger(test_session_maker, student_id)
        total_delta = sum(e.point_delta for e in entries)
        total_point = await fetch_total_point(test_session_maker, student_id)
        assert total_delta == total_point - INITIAL_POINT, (
            f"Sổ cái không khớp với total_point của sinh viên {student_id}: "
            f"delta={total_delta}, total_point={total_point}"
        )

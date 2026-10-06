"""Test hồi quy cho công thức cấm thi (`report_service.calculate_class_exam_ban`).

Bám đúng đặc tả README §4.4 / spec §4.3:
    V = N_vắng + 0.5 × N_nửa_buổi          (buổi EXCUSED không tính)
    cảnh báo lũy kế = V / số buổi ĐÃ KẾT THÚC       × 100% ≥ WARNING_ABSENCE_PERCENT
    cấm thi chính thức = V / classes.total_sessions × 100% ≥ MAX_ABSENCE_PERCENT_EXAM_BAN

Các lỗi được khoá lại ở đây:
  1. Buổi hôm nay CHƯA KẾT THÚC không được tính là "đã diễn ra" (nếu tính, mọi
     sinh viên đều bị coi là vắng buổi đó và có thể bị cấm thi oan).
  2. Ngưỡng đọc theo giờ Việt Nam (`now_vn`) chứ không phải giờ server.
  3. Ngưỡng thập phân (VD 12.5%) phải được tôn trọng, không bị bỏ qua âm thầm.
  4. Ngưỡng rác bị API từ chối 422; giá trị rác cũ trong DB vẫn fallback an toàn.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from detect_ai.modules.reporting.presentation.settings_routes import update_settings
from detect_ai.shared.kernel.security import get_password_hash
from detect_ai.shared.kernel.timeutil import VN_TZ, today_vn
from detect_ai.modules.academic.infrastructure.models import Class, ClassStudent, Schedule
from detect_ai.modules.attendance.infrastructure.models import Attendance, AttendanceStatus
from detect_ai.shared.kernel.system_setting import SystemSetting
from detect_ai.modules.identity.infrastructure.models import Role, StudentProfile, User
from detect_ai.modules.reporting.application import build as report_service
from detect_ai.modules.reporting.application.build import calculate_class_exam_ban
from detect_ai.shared.kernel.settings import load_exam_ban_thresholds


async def _seed_class(
    session: AsyncSession,
    *,
    total_sessions: int = 15,
    codes: tuple[str, ...] = ("SV001", "SV002", "SV003"),
) -> tuple[int, dict[str, int]]:
    """1 lớp học phần + N sinh viên đã ghi danh. Trả (class_id, {code: user_id})."""
    role_teacher = Role(role_name="TEACHER")
    role_student = Role(role_name="STUDENT")
    session.add_all([role_teacher, role_student])
    await session.commit()

    teacher = User(
        user_code="GV001", full_name="GV Test", email="gv@test.vn",
        password_hash=get_password_hash("x"), role_id=role_teacher.id, is_active=True,
    )
    session.add(teacher)
    await session.commit()
    await session.refresh(teacher)

    clazz = Class(
        class_code="CS101", course_name="Môn Test", teacher_id=teacher.id,
        semester="2026.1", total_sessions=total_sessions,
    )
    session.add(clazz)
    await session.commit()
    await session.refresh(clazz)

    ids: dict[str, int] = {}
    for code in codes:
        user = User(
            user_code=code, full_name=f"SV {code}", email=f"{code}@test.vn",
            password_hash=get_password_hash("x"), role_id=role_student.id, is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.add(StudentProfile(user_id=user.id, class_name="D20CNTT1", major="CNTT", total_point=100))
        session.add(ClassStudent(class_id=clazz.id, student_id=user.id))
        ids[code] = user.id
    await session.commit()
    return clazz.id, ids


async def _add_schedule(
    session: AsyncSession, class_id: int, *, study_date: date, start: time, end: time, order: int
) -> int:
    sched = Schedule(
        class_id=class_id, room_name="A101", study_date=study_date,
        start_time=start, end_time=end, session_order=order,
    )
    session.add(sched)
    await session.commit()
    await session.refresh(sched)
    return sched.id


async def _add_attendance(
    session: AsyncSession, schedule_id: int, student_id: int, status: AttendanceStatus
) -> None:
    session.add(
        Attendance(
            schedule_id=schedule_id, student_id=student_id,
            status=status, is_evaluated=True,
        )
    )
    await session.commit()


async def _three_past_sessions(session: AsyncSession, class_id: int) -> list[int]:
    """3 buổi đã kết thúc chắc chắn (cách hôm nay 1–3 ngày), 08:00–11:30."""
    return [
        await _add_schedule(
            session, class_id, study_date=today_vn() - timedelta(days=d),
            start=time(8, 0), end=time(11, 30), order=i,
        )
        for i, d in enumerate([3, 2, 1], start=1)
    ]


# --------------------------------------------------------------- biên ngưỡng
@pytest.mark.asyncio
async def test_bien_dung_20_phan_tram_bi_cam_thi(session_maker_fixture):
    """Vắng đúng 20,00% ⇒ BỊ CẤM THI (đặc tả dùng ≥); 16,67% chỉ CẢNH BÁO."""
    async with session_maker_fixture() as s:
        class_id, ids = await _seed_class(s)
        scheds = await _three_past_sessions(s, class_id)

        for sid in scheds:  # SV001: 3 vắng / 15 buổi = 20.00%
            await _add_attendance(s, sid, ids["SV001"], AttendanceStatus.ABSENT)
        # SV002: 2 vắng + 1 nửa buổi ⇒ V = 2.5 ⇒ 16.67%
        await _add_attendance(s, scheds[0], ids["SV002"], AttendanceStatus.ABSENT)
        await _add_attendance(s, scheds[1], ids["SV002"], AttendanceStatus.ABSENT)
        await _add_attendance(s, scheds[2], ids["SV002"], AttendanceStatus.HALF_ABSENT)
        # SV003: nghỉ có phép ⇒ không tính vào V
        for sid in scheds:
            await _add_attendance(s, sid, ids["SV003"], AttendanceStatus.EXCUSED)

        report = await calculate_class_exam_ban(s, class_id, reference_date=today_vn())
        rows = {r["student_code"]: r for r in report["students"]}

        assert rows["SV001"]["converted_absent"] == 3.0
        assert rows["SV001"]["rate_semester"] == 20.0
        assert rows["SV001"]["is_banned"] is True
        assert rows["SV001"]["status_label"] == "BỊ CẤM THI"

        assert rows["SV002"]["converted_absent"] == 2.5
        assert rows["SV002"]["rate_semester"] == 16.67
        assert rows["SV002"]["is_banned"] is False
        assert rows["SV002"]["status_label"] == "CẢNH BÁO"

        assert rows["SV003"]["converted_absent"] == 0.0
        assert rows["SV003"]["is_banned"] is False
        assert rows["SV003"]["is_warning"] is False
        assert rows["SV003"]["status_label"] == "ĐỦ ĐIỀU KIỆN"


@pytest.mark.asyncio
async def test_trong_so_nua_buoi_dua_sinh_vien_qua_nguong(session_maker_fixture):
    """2 vắng + 2 nửa buổi ⇒ V = 3.0 ⇒ đúng 20% ⇒ bị cấm."""
    async with session_maker_fixture() as s:
        class_id, ids = await _seed_class(s, codes=("SV001",))
        scheds = [
            await _add_schedule(
                s, class_id, study_date=today_vn() - timedelta(days=d),
                start=time(8, 0), end=time(11, 30), order=i,
            )
            for i, d in enumerate([4, 3, 2, 1], start=1)
        ]
        await _add_attendance(s, scheds[0], ids["SV001"], AttendanceStatus.ABSENT)
        await _add_attendance(s, scheds[1], ids["SV001"], AttendanceStatus.ABSENT)
        await _add_attendance(s, scheds[2], ids["SV001"], AttendanceStatus.HALF_ABSENT)
        await _add_attendance(s, scheds[3], ids["SV001"], AttendanceStatus.HALF_ABSENT)

        report = await calculate_class_exam_ban(s, class_id, reference_date=today_vn())
        row = report["students"][0]
        assert row["converted_absent"] == 3.0
        assert row["rate_semester"] == 20.0
        assert row["is_banned"] is True


# ------------------------------------------- buổi hôm nay chưa kết thúc (lỗi 1)
@pytest.mark.asyncio
async def test_buoi_hom_nay_chua_ket_thuc_khong_bi_tinh(session_maker_fixture, monkeypatch):
    """Buổi tối nay chưa tới không được cộng vào 'đã diễn ra' và không bị coi là vắng."""
    async with session_maker_fixture() as s:
        class_id, ids = await _seed_class(s, codes=("SV001",))
        scheds = [
            await _add_schedule(
                s, class_id, study_date=today_vn() - timedelta(days=d),
                start=time(8, 0), end=time(11, 30), order=i,
            )
            for i, d in enumerate([2, 1], start=1)
        ]
        for sid in scheds:  # 2 vắng thật ⇒ 2/15 = 13.33%
            await _add_attendance(s, sid, ids["SV001"], AttendanceStatus.ABSENT)
        # Buổi hôm nay 23:00–23:45, chưa có bản ghi điểm danh nào.
        await _add_schedule(
            s, class_id, study_date=today_vn(), start=time(23, 0), end=time(23, 45), order=3,
        )

        # 12:00 hôm nay: buổi tối chưa kết thúc ⇒ chỉ 2 buổi đã diễn ra.
        monkeypatch.setattr(
            report_service, "now_vn",
            lambda: datetime.combine(today_vn(), time(12, 0), tzinfo=VN_TZ),
        )
        report = await calculate_class_exam_ban(s, class_id, reference_date=today_vn())
        row = report["students"][0]
        assert report["elapsed_sessions"] == 2
        assert row["absent_count"] == 2
        assert row["rate_semester"] == 13.33
        assert row["is_banned"] is False

        # 23:50 hôm nay: buổi tối đã kết thúc và không có bản ghi ⇒ tính là vắng.
        monkeypatch.setattr(
            report_service, "now_vn",
            lambda: datetime.combine(today_vn(), time(23, 50), tzinfo=VN_TZ),
        )
        report = await calculate_class_exam_ban(s, class_id, reference_date=today_vn())
        row = report["students"][0]
        assert report["elapsed_sessions"] == 3
        assert row["absent_count"] == 3
        assert row["rate_semester"] == 20.0
        assert row["is_banned"] is True


# ------------------------------------------------------- ngưỡng thập phân (lỗi 3)
@pytest.mark.asyncio
async def test_nguong_thap_phan_duoc_ton_trong(session_maker_fixture):
    """Admin đặt 12.5% thì 12.5% là ngưỡng thật, không quay về mặc định 20%."""
    async with session_maker_fixture() as s:
        class_id, ids = await _seed_class(s, codes=("SV001", "SV002"))
        scheds = await _three_past_sessions(s, class_id)
        s.add_all([
            SystemSetting(key="WARNING_ABSENCE_PERCENT", value="5"),
            SystemSetting(key="MAX_ABSENCE_PERCENT_EXAM_BAN", value="12.5"),
        ])
        await s.commit()

        # SV001: 2 vắng ⇒ 13.33% ≥ 12.5% ⇒ cấm
        await _add_attendance(s, scheds[0], ids["SV001"], AttendanceStatus.ABSENT)
        await _add_attendance(s, scheds[1], ids["SV001"], AttendanceStatus.ABSENT)
        await _add_attendance(s, scheds[2], ids["SV001"], AttendanceStatus.PRESENT)
        # SV002: 1 vắng + 1 nửa buổi ⇒ V = 1.5 ⇒ 10% ⇒ chưa cấm, chỉ cảnh báo
        await _add_attendance(s, scheds[0], ids["SV002"], AttendanceStatus.ABSENT)
        await _add_attendance(s, scheds[1], ids["SV002"], AttendanceStatus.HALF_ABSENT)
        await _add_attendance(s, scheds[2], ids["SV002"], AttendanceStatus.PRESENT)

        report = await calculate_class_exam_ban(s, class_id, reference_date=today_vn())
        assert report["warning_percent"] == 5.0
        assert report["ban_percent"] == 12.5
        rows = {r["student_code"]: r for r in report["students"]}
        assert rows["SV001"]["rate_semester"] == 13.33
        assert rows["SV001"]["is_banned"] is True
        assert rows["SV002"]["rate_semester"] == 10.0
        assert rows["SV002"]["is_banned"] is False
        assert rows["SV002"]["is_warning"] is True


# ------------------------------------------------- ngưỡng rác bị chặn (lỗi 4)
@pytest.mark.asyncio
async def test_api_tu_choi_nguong_khong_hop_le(session_maker_fixture):
    """API cấu hình trả 422 cho ngưỡng không phải số / ngoài 0–100; nhận số thập phân."""
    async with session_maker_fixture() as s:
        with pytest.raises(HTTPException) as exc_chu:
            await update_settings({"MAX_ABSENCE_PERCENT_EXAM_BAN": "hai mươi"}, s)
        assert exc_chu.value.status_code == 422

        with pytest.raises(HTTPException) as exc_range:
            await update_settings({"WARNING_ABSENCE_PERCENT": "150"}, s)
        assert exc_range.value.status_code == 422

        with pytest.raises(HTTPException) as exc_empty:
            await update_settings({"WARNING_ABSENCE_PERCENT": ""}, s)
        assert exc_empty.value.status_code == 422

        response = await update_settings({"MAX_ABSENCE_PERCENT_EXAM_BAN": "12.5"}, s)
        assert response.settings["MAX_ABSENCE_PERCENT_EXAM_BAN"] == "12.5"


@pytest.mark.asyncio
async def test_gia_tri_rac_trong_db_van_fallback_an_toan(session_maker_fixture):
    """Dữ liệu cũ/hỏng trong system_settings không được làm sập hay lệch công thức."""
    async with session_maker_fixture() as s:
        s.add(SystemSetting(key="MAX_ABSENCE_PERCENT_EXAM_BAN", value="abc"))
        await s.commit()
        assert await load_exam_ban_thresholds(s) == (15.0, 20.0)

        s.add(SystemSetting(key="WARNING_ABSENCE_PERCENT", value="12.5"))
        await s.commit()
        assert await load_exam_ban_thresholds(s) == (12.5, 20.0)


def test_report_weight_matches_policy():
    from detect_ai.modules.reporting.application import build as rs
    from detect_ai.modules.evaluation.domain import exam_ban as pol
    assert rs.HALF_ABSENT_WEIGHT == pol.HALF_ABSENT_WEIGHT == 0.5

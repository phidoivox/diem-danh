"""Leave-review use-case (Task 7 / Task 3).

Giữ đúng thứ tự routes_leave_requests.py:291-358:
  đổi status -> tìm/tạo EXCUSED -> check is_evaluated ->
  check LEAVE_REFUND đã có -> cộng total_point ->
  commit, lỗi rollback, refresh trả về model cho route dựng DTO.
Route chỉ còn validate (404 + quyền sở hữu) -> gọi use-case -> trả DTO.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from detect_ai.modules.attendance.public import Attendance, AttendanceStatus
from detect_ai.modules.evaluation.public import PointLedger
from ..infrastructure.models import (
    LeaveRequest,
    LeaveStatus,
    find_attendance,
    find_refund_entry,
    find_student_profile,
    list_deduct_ledger_entries,
)


async def review_leave(
    session: Any,
    *,
    leave: LeaveRequest,
    new_status: LeaveStatus,
    feedback: str | None,
    reviewer_id: int,
) -> LeaveRequest:
    """Duyệt đơn nghỉ phép, xử lý hoàn điểm duyệt muộn. Trả leave đã refresh."""
    # 3. Cập nhật trạng thái đơn (đúng thứ tự route cũ).
    leave.status = new_status
    leave.teacher_feedback = feedback.strip() if feedback else None
    leave.reviewed_by = reviewer_id
    leave.reviewed_at = datetime.now(timezone.utc)

    # 4. Nghiệp vụ phê duyệt (APPROVED).
    if new_status == LeaveStatus.APPROVED:
        # 4.1 Tìm hoặc tạo bản ghi attendance EXCUSED.
        attendance = await find_attendance(session, leave.schedule_id, leave.student_id)

        if not attendance:
            attendance = Attendance(
                schedule_id=leave.schedule_id,
                student_id=leave.student_id,
                status=AttendanceStatus.EXCUSED,
            )
            session.add(attendance)
        else:
            attendance.status = AttendanceStatus.EXCUSED

        # 4.2 Cơ chế Hoàn điểm duyệt muộn (Late Approval Refund Logic).
        if attendance and attendance.is_evaluated:
            deduct_records = await list_deduct_ledger_entries(
                session, leave.student_id, leave.schedule_id
            )

            # Tránh hoàn điểm 2 lần.
            already_refunded = await find_refund_entry(
                session, leave.student_id, leave.schedule_id
            )

            if deduct_records and not already_refunded:
                refund_points = sum(abs(r.point_delta) for r in deduct_records)
                clazz = leave.schedule.clazz if leave.schedule else None
                class_code_str = clazz.class_code if clazz else ""

                refund_entry = PointLedger(
                    student_id=leave.student_id,
                    schedule_id=leave.schedule_id,
                    point_delta=refund_points,
                    reason_code="LEAVE_REFUND",
                    description=(
                        "Hoàn điểm chuyên cần do đơn nghỉ phép được duyệt bổ sung "
                        f"(Lớp {class_code_str})"
                    ),
                )
                profile = await find_student_profile(session, leave.student_id)
                if profile:
                    _old = profile.total_point
                    if _old is None:
                        _old = 100 if bool(getattr(profile, "is_officer", False)) else 95
                    _new = min(100, max(0, _old + refund_points))
                    refund_entry.point_delta = _new - _old
                    profile.total_point = _new
                else:
                    # Không có profile: kẹp refund trên nền 100 để ledger
                    # không bao giờ vượt 0..100.
                    _new = min(100, max(0, 100 + refund_points))
                    refund_entry.point_delta = _new - 100
                session.add(refund_entry)

    # 5. Dao hoan diem khi chuyen APPROVED -> REJECTED (chong phong total_point).
    if new_status == LeaveStatus.REJECTED:
        already_refunded = await find_refund_entry(
            session, leave.student_id, leave.schedule_id
        )
        if already_refunded is not None:
            profile = await find_student_profile(session, leave.student_id)
            if profile is not None:
                _old = profile.total_point
                if _old is None:
                    _old = 100 if bool(getattr(profile, "is_officer", False)) else 95
                _new = min(100, max(0, _old + already_refunded.point_delta))
                profile.total_point = _new
            await session.delete(already_refunded)
        # Tu REJECTED ve: attendance EXCUSED cu -> ve ABSENT cho cron cham lai.
        attendance = await find_attendance(session, leave.schedule_id, leave.student_id)
        if attendance is not None and attendance.status == AttendanceStatus.EXCUSED:
            attendance.status = AttendanceStatus.ABSENT
            attendance.is_evaluated = False

    try:
        await session.commit()
        await session.refresh(leave)
    except Exception:
        await session.rollback()
        raise
    return leave


__all__ = ["review_leave"]

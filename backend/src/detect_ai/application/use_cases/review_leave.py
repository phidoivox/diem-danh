"""Leave-review use-case (Task 7).

Giữ đúng thứ tự routes_leave_requests.py:291-358:
  đổi status -> tìm/tạo EXCUSED -> check is_evaluated ->
  check LEAVE_REFUND đã có -> cộng total_point ->
  commit, lỗi rollback, refresh trả về model cho route dựng DTO.
Route chỉ còn validate (404 + quyền sở hữu) -> gọi use-case -> trả DTO.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.attendance_v2 import Attendance, AttendanceStatus
from ...models.leave_request import LeaveRequest, LeaveStatus
from ...models.point_ledger import PointLedger
from ...models.user import StudentProfile


async def review_leave(
    session: AsyncSession,
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
        att_stmt = select(Attendance).where(
            Attendance.schedule_id == leave.schedule_id,
            Attendance.student_id == leave.student_id,
        )
        attendance = (await session.execute(att_stmt)).scalar_one_or_none()

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
            ledger_stmt = select(PointLedger).where(
                PointLedger.student_id == leave.student_id,
                PointLedger.schedule_id == leave.schedule_id,
                PointLedger.point_delta < 0,
            )
            deduct_records = (await session.execute(ledger_stmt)).scalars().all()

            # Tránh hoàn điểm 2 lần.
            refund_check_stmt = select(PointLedger).where(
                PointLedger.student_id == leave.student_id,
                PointLedger.schedule_id == leave.schedule_id,
                PointLedger.reason_code == "LEAVE_REFUND",
            )
            already_refunded = (await session.execute(refund_check_stmt)).scalar_one_or_none()

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
                session.add(refund_entry)

                sp_stmt = select(StudentProfile).where(
                    StudentProfile.user_id == leave.student_id
                )
                profile = (await session.execute(sp_stmt)).scalar_one_or_none()
                if profile:
                    profile.total_point += refund_points

    try:
        await session.commit()
        await session.refresh(leave)
    except Exception:
        await session.rollback()
        raise
    return leave

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.academic import ClassStudent, Schedule
from ..models.attendance_v2 import Attendance, AttendanceStatus
from ..models.leave_request import LeaveRequest, LeaveStatus
from ..models.point_ledger import PointLedger
from ..models.user import StudentProfile
from .settings_repo import as_bool, as_int, load_settings_map


async def run_nightly_evaluation(
    session: AsyncSession,
    target_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Execute nightly evaluation of student attendance for the target date.
    
    This function is strictly idempotent: only attendance records with is_evaluated == False
    are evaluated and written to the point ledger. Running multiple times will not duplicate points.
    """
    if target_date is None:
        target_date = date.today()

    logger.info(f"Running nightly evaluation for target_date={target_date}")

    # 1. Read system settings
    settings_map = await load_settings_map(session)

    point_full = as_int(settings_map, "POINT_FULL_ATTENDANCE", 2)
    point_late = as_int(settings_map, "POINT_LATE", -1)
    point_half_absence = as_int(settings_map, "POINT_HALF_ABSENCE", -2)
    point_absence_without_leave = as_int(settings_map, "POINT_ABSENCE_WITHOUT_LEAVE", -5)
    point_uniform_violation = as_int(settings_map, "POINT_UNIFORM_VIOLATION", -2)
    late_tolerance_minutes = as_int(settings_map, "LATE_TOLERANCE_MINUTES", 15)
    require_checkout = as_bool(settings_map, "REQUIRE_CHECKOUT", True)

    # Bảng quy đổi trạng thái -> điểm (thay if/elif 5 nhánh lặp 2 lần).
    POINT_MAP = {
        AttendanceStatus.PRESENT: point_full,
        AttendanceStatus.LATE: point_late,
        AttendanceStatus.HALF_ABSENT: point_half_absence,
        AttendanceStatus.ABSENT: point_absence_without_leave,
        AttendanceStatus.EXCUSED: 0,
    }

    # 2. Query schedules for target_date
    stmt_schedules = (
        select(Schedule)
        .where(Schedule.study_date == target_date)
        .order_by(Schedule.id)
    )
    schedules = (await session.execute(stmt_schedules)).scalars().all()

    count_records = 0
    evaluated_student_ids: Set[int] = set()
    evaluated_schedule_ids: Set[int] = set()

    for sched in schedules:
        # A. Find all enrolled students in the schedule's class
        stmt_enrolled = select(ClassStudent.student_id).where(
            ClassStudent.class_id == sched.class_id
        )
        enrolled_student_ids = (await session.execute(stmt_enrolled)).scalars().all()

        # B. Find existing attendances for this schedule
        stmt_existing = select(Attendance).where(Attendance.schedule_id == sched.id)
        existing_attendances = (await session.execute(stmt_existing)).scalars().all()
        att_by_student = {att.student_id: att for att in existing_attendances}

        # C. Auto-create ABSENT attendance for students without any record
        for sid in enrolled_student_ids:
            if sid not in att_by_student:
                new_att = Attendance(
                    schedule_id=sched.id,
                    student_id=sid,
                    status=AttendanceStatus.ABSENT,
                    is_evaluated=False,
                    has_uniform=True,
                    is_manual_override=False,
                )
                session.add(new_att)
                att_by_student[sid] = new_att

        await session.flush()

        # D. Filter attendances that are not evaluated yet (ensure Idempotency)
        unevaluated_attendances = [
            att for att in att_by_student.values() if not att.is_evaluated
        ]

        if not unevaluated_attendances:
            continue

        sched_start_dt = datetime.combine(sched.study_date, sched.start_time)
        late_deadline = sched_start_dt + timedelta(minutes=late_tolerance_minutes)

        # Bulk fetch: 1 query profiles + 1 query approved-leaves cho cả buổi
        # (thay N+1 query trong loop từng sinh viên).
        uneval_ids = [att.student_id for att in unevaluated_attendances]
        profiles = (
            (await session.execute(
                select(StudentProfile).where(StudentProfile.user_id.in_(uneval_ids))
            )).scalars().all()
        )
        profile_by_student = {p.user_id: p for p in profiles}
        approved_ids = set(
            (await session.execute(
                select(LeaveRequest.student_id).where(
                    LeaveRequest.schedule_id == sched.id,
                    LeaveRequest.student_id.in_(uneval_ids),
                    LeaveRequest.status == LeaveStatus.APPROVED,
                )
            )).scalars().all()
        )

        for att in unevaluated_attendances:
            profile = profile_by_student.get(att.student_id)

            point_delta = 0

            # Rule 1: Respect manual override by teacher
            if att.is_manual_override:
                point_delta = POINT_MAP.get(att.status, 0)
                # Uniform violation applies if has_uniform is False and status != EXCUSED
                if not att.has_uniform and att.status != AttendanceStatus.EXCUSED:
                    point_delta += point_uniform_violation

            else:
                # Rule 2: Check approved leave requests (đã bulk-fetch ở trên)
                if att.student_id in approved_ids:
                    att.status = AttendanceStatus.EXCUSED
                    point_delta = 0
                else:
                    # Rule 3: Auto-inference from check-in/check-out records
                    if att.check_in_time is not None:
                        cin = att.check_in_time
                        cin_naive = (
                            datetime.combine(cin.date(), cin.time())
                            if cin.tzinfo is not None
                            else cin
                        )
                        is_late = cin_naive > late_deadline

                        if require_checkout:
                            if att.check_out_time is not None:
                                if is_late:
                                    att.status = AttendanceStatus.LATE
                                    point_delta = point_late
                                else:
                                    att.status = AttendanceStatus.PRESENT
                                    point_delta = point_full
                            else:
                                att.status = AttendanceStatus.HALF_ABSENT
                                point_delta = point_half_absence
                        else:
                            if is_late:
                                att.status = AttendanceStatus.LATE
                                point_delta = point_late
                            else:
                                att.status = AttendanceStatus.PRESENT
                                point_delta = point_full

                        # Uniform violation check
                        if not att.has_uniform:
                            point_delta += point_uniform_violation
                    else:
                        # No check-in recorded
                        att.status = AttendanceStatus.ABSENT
                        point_delta = point_absence_without_leave

            # Record in Point Ledger
            ledger_entry = PointLedger(
                student_id=att.student_id,
                schedule_id=sched.id,
                point_delta=point_delta,
                reason_code="NIGHTLY_EVAL",
                description=f"Đánh giá chuyên cần ngày {target_date} - {att.status.value}",
            )
            session.add(ledger_entry)

            # Mark attendance evaluated
            att.is_evaluated = True
            att.evaluated_at = datetime.now(timezone.utc)

            # Update profile total_point
            if profile:
                profile.total_point = max(0, profile.total_point + point_delta)

            count_records += 1
            evaluated_student_ids.add(att.student_id)
            evaluated_schedule_ids.add(sched.id)

    await session.commit()

    stats = {
        "target_date": str(target_date),
        "schedules_evaluated": len(evaluated_schedule_ids),
        "students_evaluated": len(evaluated_student_ids),
        "total_records": count_records,
    }
    logger.info(f"Evaluation complete for {target_date}: {stats}")
    return stats

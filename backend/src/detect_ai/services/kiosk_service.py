from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.academic import ClassStudent, Schedule
from ..models.attendance_v2 import Attendance, AttendanceStatus
from ..models.system_setting import SystemSetting
from ..models.user import User


async def record_kiosk_attendance(
    s: AsyncSession,
    room_name: str,
    student_code: str,
    has_uniform: bool,
    scan_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Process real-time attendance scan from Kiosk AI terminal (Check-in / Check-out)."""
    # 1. Normalize scan_time
    if scan_time is None:
        scan_time = datetime.now(timezone.utc)
    elif scan_time.tzinfo is None:
        scan_time = scan_time.replace(tzinfo=timezone.utc)

    # 2. Find student by user_code
    stmt_student = (
        select(User)
        .options(selectinload(User.student_profile))
        .where(
            User.user_code == student_code,
            User.is_active == True,
            User.deleted_at.is_(None),
        )
    )
    student = (await s.execute(stmt_student)).scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sinh viên có mã {student_code}",
        )

    # 3. Find Schedule currently active in room within 30-minute buffer
    scan_date = scan_time.date()
    scan_dt_naive = datetime.combine(scan_date, scan_time.time())

    stmt_schedules = (
        select(Schedule)
        .options(selectinload(Schedule.clazz))
        .where(
            Schedule.room_name == room_name,
            Schedule.study_date == scan_date,
        )
    )
    day_schedules = (await s.execute(stmt_schedules)).scalars().all()

    matching_schedules: List[Schedule] = []
    for sched in day_schedules:
        start_dt = datetime.combine(sched.study_date, sched.start_time) - timedelta(minutes=30)
        end_dt = datetime.combine(sched.study_date, sched.end_time) + timedelta(minutes=30)
        if start_dt <= scan_dt_naive <= end_dt:
            matching_schedules.append(sched)

    if not matching_schedules:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy buổi học nào đang diễn ra tại phòng {room_name}",
        )

    # If multiple schedules match buffer window, prioritize the one student is enrolled in
    if len(matching_schedules) == 1:
        target_sched = matching_schedules[0]
    else:
        candidate_class_ids = [sc.class_id for sc in matching_schedules]
        enrolled_stmt = select(ClassStudent.class_id).where(
            ClassStudent.class_id.in_(candidate_class_ids),
            ClassStudent.student_id == student.id,
        )
        enrolled_ids = set((await s.execute(enrolled_stmt)).scalars().all())
        enrolled_matches = [sc for sc in matching_schedules if sc.class_id in enrolled_ids]
        if enrolled_matches:
            target_sched = min(
                enrolled_matches,
                key=lambda sc: min(
                    abs((datetime.combine(sc.study_date, sc.start_time) - scan_dt_naive).total_seconds()),
                    abs((datetime.combine(sc.study_date, sc.end_time) - scan_dt_naive).total_seconds()),
                ),
            )
        else:
            target_sched = matching_schedules[0]

    # 4. Validate student enrollment in class
    stmt_enroll = select(ClassStudent).where(
        ClassStudent.class_id == target_sched.class_id,
        ClassStudent.student_id == student.id,
    )
    is_enrolled = (await s.execute(stmt_enroll)).scalar_one_or_none() is not None
    if not is_enrolled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sinh viên không có tên trong danh sách lớp của ca học này",
        )

    # 5. Read late tolerance minutes from system settings
    stmt_setting = select(SystemSetting.value).where(SystemSetting.key == "LATE_TOLERANCE_MINUTES")
    setting_val = (await s.execute(stmt_setting)).scalar_one_or_none()
    late_tolerance_minutes = int(setting_val) if setting_val and setting_val.isdigit() else 15

    class_code = target_sched.clazz.class_code if target_sched.clazz else ""

    # 6. Find or create Attendance record
    stmt_att = select(Attendance).where(
        Attendance.schedule_id == target_sched.id,
        Attendance.student_id == student.id,
    )
    attendance = (await s.execute(stmt_att)).scalar_one_or_none()

    sched_start_dt = datetime.combine(target_sched.study_date, target_sched.start_time)
    late_deadline = sched_start_dt + timedelta(minutes=late_tolerance_minutes)

    if attendance is None or attendance.check_in_time is None:
        # Case 1: Check-in
        initial_status = (
            AttendanceStatus.PRESENT
            if scan_dt_naive <= late_deadline
            else AttendanceStatus.LATE
        )

        if attendance is None:
            attendance = Attendance(
                schedule_id=target_sched.id,
                student_id=student.id,
                check_in_time=scan_time,
                has_uniform=has_uniform,
                status=initial_status,
                is_manual_override=False,
                is_evaluated=False,
            )
            s.add(attendance)
        else:
            attendance.check_in_time = scan_time
            attendance.has_uniform = has_uniform
            attendance.status = initial_status
            attendance.is_manual_override = False
            attendance.is_evaluated = False

        await s.commit()
        await s.refresh(attendance)

        return {
            "type": "CHECK_IN",
            "student_code": student_code,
            "student_name": student.full_name,
            "room_name": room_name,
            "class_code": class_code,
            "status": attendance.status.value,
            "has_uniform": has_uniform,
            "time": scan_time.isoformat(),
        }
    else:
        # Case 2: Check-out
        attendance.check_out_time = scan_time
        # Uniform violation during either check-in or check-out is maintained
        attendance.has_uniform = bool(has_uniform and attendance.has_uniform)

        await s.commit()
        await s.refresh(attendance)

        return {
            "type": "CHECK_OUT",
            "student_code": student_code,
            "student_name": student.full_name,
            "room_name": room_name,
            "class_code": class_code,
            "check_in_time": attendance.check_in_time.isoformat(),
            "check_out_time": scan_time.isoformat(),
            "has_uniform": attendance.has_uniform,
        }

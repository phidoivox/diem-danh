from __future__ import annotations

from datetime import date, datetime, time
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from detect_ai.shared.kernel.deps import get_db
from detect_ai.modules.academic.public import Class, ClassStudent, Schedule
from detect_ai.modules.attendance.public import Attendance, AttendanceStatus
from detect_ai.modules.evaluation.public import PointLedger, classify_conduct
from detect_ai.modules.identity.public import StudentProfile, User, require_role

router = APIRouter(prefix="/api/v1/student", tags=["student-portal"])


# =====================================================================
# SCHEMAS
# =====================================================================
class StudentScheduleItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    class_id: int
    class_code: str
    course_name: str
    teacher_name: str
    room_name: str
    study_date: date
    start_time: time
    end_time: time
    session_order: int


class StudentAttendanceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attendance_id: int
    schedule_id: int
    class_code: str
    course_name: str
    study_date: date
    start_time: time
    end_time: time
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    has_uniform: bool
    status: str
    note: Optional[str] = None
    snapshot_url: Optional[str] = None


class ConductLedgerEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    point_delta: int
    reason_code: str
    description: Optional[str] = None
    created_at: datetime
    schedule_id: Optional[int] = None


class StudentConductLedgerResponse(BaseModel):
    total_point: int
    conduct_rank: str
    is_officer: bool = False
    items: List[ConductLedgerEntry]


# =====================================================================
# ENDPOINTS
# =====================================================================
@router.get(
    "/schedule",
    response_model=List[StudentScheduleItem],
    summary="Sinh viên xem thời khóa biểu các lớp đang theo học",
)
async def get_student_schedule(
    current_user: User = Depends(require_role("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Schedule)
        .join(Class, Schedule.class_id == Class.id)
        .join(ClassStudent, Class.id == ClassStudent.class_id)
        .options(selectinload(Schedule.clazz).selectinload(Class.teacher))
        .where(ClassStudent.student_id == current_user.id)
        .order_by(Schedule.study_date.asc(), Schedule.start_time.asc())
    )
    result = await db.execute(stmt)
    schedules = result.scalars().all()

    items = []
    for sched in schedules:
        clazz = sched.clazz
        teacher_name = clazz.teacher.full_name if (clazz and clazz.teacher) else ""
        items.append(
            StudentScheduleItem(
                id=sched.id,
                class_id=sched.class_id,
                class_code=clazz.class_code if clazz else "",
                course_name=clazz.course_name if clazz else "",
                teacher_name=teacher_name,
                room_name=sched.room_name,
                study_date=sched.study_date,
                start_time=sched.start_time,
                end_time=sched.end_time,
                session_order=sched.session_order,
            )
        )
    return items


@router.get(
    "/attendance",
    response_model=List[StudentAttendanceItem],
    summary="Sinh viên xem lịch sử điểm danh cá nhân",
)
async def get_student_attendance(
    current_user: User = Depends(require_role("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Attendance)
        .join(Schedule, Attendance.schedule_id == Schedule.id)
        .join(Class, Schedule.class_id == Class.id)
        .options(selectinload(Attendance.schedule).selectinload(Schedule.clazz))
        .where(Attendance.student_id == current_user.id)
        .order_by(Schedule.study_date.desc(), Schedule.start_time.desc())
    )
    result = await db.execute(stmt)
    attendances = result.scalars().all()

    items = []
    for att in attendances:
        sched = att.schedule
        clazz = sched.clazz if sched else None
        status_val = att.status.value if isinstance(att.status, AttendanceStatus) else str(att.status)
        items.append(
            StudentAttendanceItem(
                attendance_id=att.id,
                schedule_id=att.schedule_id,
                class_code=clazz.class_code if clazz else "",
                course_name=clazz.course_name if clazz else "",
                study_date=sched.study_date if sched else date.today(),
                start_time=sched.start_time if sched else time(0, 0),
                end_time=sched.end_time if sched else time(0, 0),
                check_in_time=att.check_in_time,
                check_out_time=att.check_out_time,
                has_uniform=att.has_uniform,
                status=status_val,
                note=att.note,
                snapshot_url=att.check_in_snapshot_url or att.check_out_snapshot_url,
            )
        )
    return items


@router.get(
    "/conduct-ledger",
    response_model=StudentConductLedgerResponse,
    summary="Sinh viên xem điểm rèn luyện hiện tại và sổ cái biến động điểm",
)
async def get_student_conduct_ledger(
    current_user: User = Depends(require_role("STUDENT")),
    db: AsyncSession = Depends(get_db),
):
    # Lấy điểm hiện tại từ student_profiles (mặc định SV 95, cán sự 100).
    total_point = 100
    is_officer = False
    sp_stmt = select(StudentProfile).where(StudentProfile.user_id == current_user.id)
    sp_res = await db.execute(sp_stmt)
    profile = sp_res.scalar_one_or_none()
    if profile:
        is_officer = bool(profile.is_officer)
        total_point = profile.total_point if profile.total_point is not None else (100 if is_officer else 95)
    elif current_user.student_profile:
        is_officer = bool(getattr(current_user.student_profile, "is_officer", False))
        total_point = current_user.student_profile.total_point
        if total_point is None:
            total_point = 100 if is_officer else 95

    # Lấy sổ cái biến động điểm
    ledger_stmt = (
        select(PointLedger)
        .where(PointLedger.student_id == current_user.id)
        .order_by(PointLedger.created_at.desc(), PointLedger.id.desc())
    )
    ledger_res = await db.execute(ledger_stmt)
    entries = ledger_res.scalars().all()

    items = [
        ConductLedgerEntry(
            id=entry.id,
            point_delta=entry.point_delta,
            reason_code=entry.reason_code,
            description=entry.description,
            created_at=entry.created_at,
            schedule_id=entry.schedule_id,
        )
        for entry in entries
    ]

    return StudentConductLedgerResponse(
        total_point=total_point,
        conduct_rank=classify_conduct(total_point, is_officer),
        is_officer=is_officer,
        items=items,
    )

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.deps import get_db
from ..core.timeutil import VN_TZ as _VN_TZ
from ..core.timeutil import today_vn as _today_vn
from ..models.academic import Class, ClassStudent, Schedule
from ..models.attendance_v2 import Attendance, AttendanceStatus
from ..models.point_ledger import PointLedger
from ..models.user import User
from ..services.report_service import (
    calculate_class_exam_ban,
    generate_excel_exam_ban,
)
from .deps_auth import require_teacher
from .helpers import get_or_404

router = APIRouter(
    prefix="/api/v1/teacher",
    tags=["teacher"],
    dependencies=[Depends(require_teacher)],
)


# =====================================================================
# SCHEMAS
# =====================================================================


def _current_session(
    schedules: List[Schedule], now: Optional[datetime] = None
) -> Optional[Schedule]:
    """Chọn buổi đang diễn ra (start <= now < end), nếu chưa tới giờ thì
    lấy buổi sắp tới gần nhất, ngược lại lấy buổi cuối cùng trong ngày.

    Trước đây chỗ này luôn lấy buổi đầu tiên (`.first()` sau `ORDER BY
    start_time`), nên lớp học cả sáng + chiều thì buổi chiều vẫn dính
    điểm danh/attendance của buổi sáng.
    """
    if not schedules:
        return None
    ordered = sorted(schedules, key=lambda s: (s.start_time, s.end_time, s.id))
    current = (now or datetime.now(_VN_TZ)).time().replace(tzinfo=None)
    for s in ordered:
        start = s.start_time.replace(tzinfo=None) if s.start_time else None
        end = s.end_time.replace(tzinfo=None) if s.end_time else None
        if start is not None and end is not None and start <= current < end:
            return s
    upcoming = [s for s in ordered if s.start_time and s.start_time.replace(tzinfo=None) > current]
    if upcoming:
        return upcoming[0]
    return ordered[-1]


class ScheduleBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    study_date: date
    start_time: str
    end_time: str
    room_name: str
    session_order: int


class TeacherClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    class_code: str
    course_name: str
    teacher_id: int
    semester: str
    total_sessions: int
    student_count: int
    today_schedule: Optional[ScheduleBrief] = None


class StudentAttendanceLiveItem(BaseModel):
    attendance_id: Optional[int] = None
    student_id: int
    student_code: str
    full_name: str
    class_name: Optional[str] = ""
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    check_in_snapshot_url: Optional[str] = None
    check_out_snapshot_url: Optional[str] = None
    has_uniform: bool = True
    status: str
    is_manual_override: bool = False
    # Nguồn điểm danh: face (kiosk khuôn mặt) | manual (GV sửa) | teacher (GV tick) | none.
    source: str = "none"


def _attendance_source(att) -> str:
    if att is None:
        return "none"
    if att.is_manual_override:
        return "manual"
    if (att.note or "") and "face-kiosk" in att.note:
        return "face"
    return "teacher"


class LiveAttendanceResponse(BaseModel):
    class_id: int
    class_code: str
    course_name: str
    schedule_id: Optional[int] = None
    study_date: Optional[date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room_name: Optional[str] = None
    total_students: int
    checked_in_count: int
    absent_count: int
    uniform_violation_count: int
    students: List[StudentAttendanceLiveItem]


class ManualOverrideRequest(BaseModel):
    status: AttendanceStatus
    note: Optional[str] = Field("", max_length=255)
    schedule_id: Optional[int] = None
    student_id: Optional[int] = None


class AttendanceDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int
    student_id: int
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    check_in_snapshot_url: Optional[str] = None
    check_out_snapshot_url: Optional[str] = None
    has_uniform: bool
    status: str
    is_manual_override: bool
    note: Optional[str] = None
    updated_by: Optional[int] = None


class StudentHistoryItem(BaseModel):
    schedule_id: int
    study_date: date
    start_time: str
    end_time: str
    session_order: int
    room_name: str
    attendance_id: Optional[int] = None
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    check_in_snapshot_url: Optional[str] = None
    check_out_snapshot_url: Optional[str] = None
    has_uniform: bool = True
    status: str = "ABSENT"
    is_manual_override: bool = False
    source: str = "none"
    note: Optional[str] = None
    # Tổng biến động điểm rèn luyện của buổi học này (sum point_ledger
    # theo schedule_id + student_id). None = chưa được cron chấm điểm.
    point_delta: Optional[int] = None


class StudentHistorySummary(BaseModel):
    total_sessions: int = 0
    present: int = 0
    late: int = 0
    half_absent: int = 0
    absent: int = 0
    excused: int = 0
    # Tổng điểm bị trừ (cộng gộp các point_delta âm) trong phạm vi lớp này.
    total_deducted: int = 0


class StudentHistoryResponse(BaseModel):
    class_id: int
    class_code: str
    course_name: str
    student_id: int
    student_code: str
    full_name: str
    summary: StudentHistorySummary
    items: List[StudentHistoryItem]


# =====================================================================
# ROUTES
# =====================================================================
@router.get(
    "/classes",
    response_model=List[TeacherClassResponse],
    summary="Danh sách các lớp học phần do giảng viên đang đăng nhập phụ trách",
)
async def get_teacher_classes(
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Class,
            func.count(ClassStudent.student_id).label("student_count"),
        )
        .outerjoin(ClassStudent, ClassStudent.class_id == Class.id)
        .options(selectinload(Class.course))
        .where(Class.teacher_id == current_user.id)
        .group_by(Class.id)
        .order_by(Class.class_code)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Lấy tiết dạy hôm nay (nếu có) của các lớp này.
    # Một lớp có thể học 2 buổi/ngày (sáng + chiều) nên phải chọn đúng buổi
    # theo giờ hiện tại, không lấy cứng buổi đầu tiên.
    today = _today_vn()
    now_vn = datetime.now(_VN_TZ)
    sched_stmt = (
        select(Schedule)
        .join(Class, Class.id == Schedule.class_id)
        .where(Class.teacher_id == current_user.id, Schedule.study_date == today)
        .order_by(Schedule.start_time)
    )
    sched_rows = (await db.execute(sched_stmt)).scalars().all()
    by_class: Dict[int, List[Schedule]] = {}
    for s in sched_rows:
        by_class.setdefault(s.class_id, []).append(s)
    today_sched_by_class: Dict[int, Schedule] = {
        class_id: cur
        for class_id, schedules in by_class.items()
        if (cur := _current_session(schedules, now_vn)) is not None
    }

    items = []
    for clazz, count in rows:
        today_s = today_sched_by_class.get(clazz.id)
        today_sched = None
        if today_s:
            st_str = today_s.start_time.strftime("%H:%M") if hasattr(today_s.start_time, "strftime") else str(today_s.start_time)
            et_str = today_s.end_time.strftime("%H:%M") if hasattr(today_s.end_time, "strftime") else str(today_s.end_time)
            today_sched = ScheduleBrief(
                id=today_s.id,
                study_date=today_s.study_date,
                start_time=st_str,
                end_time=et_str,
                room_name=today_s.room_name,
                session_order=today_s.session_order,
            )

        items.append(
            TeacherClassResponse(
                id=clazz.id,
                class_code=clazz.class_code,
                course_name=clazz.course_name,
                teacher_id=clazz.teacher_id,
                semester=clazz.semester,
                total_sessions=clazz.total_sessions,
                student_count=count,
                today_schedule=today_sched,
            )
        )
    return items


@router.get(
    "/classes/{class_id}/live-attendance",
    response_model=LiveAttendanceResponse,
    summary="Xem sĩ số và trạng thái điểm danh thời gian thực của lớp",
)
async def get_class_live_attendance(
    class_id: int,
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    class_obj = (
        await db.execute(
            select(Class).options(selectinload(Class.course)).where(Class.id == class_id)
        )
    ).scalar_one_or_none()
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy lớp học phần",
        )

    if class_obj.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền quản lý lớp học này",
        )

    # 1. Chỉ mở điểm danh khi có tiết: đúng ngày hôm nay mới có buổi học.
    # Một lớp có thể học 2 buổi/ngày (sáng + chiều) nên phải chọn đúng buổi
    # theo giờ hiện tại, không lấy cứng buổi đầu tiên.
    # Không fallback quá khứ/tương lai — ngoài tiết thì schedule_id=None (kiosk đóng),
    # GV vẫn xem được danh sách SV và sửa tay.
    today = _today_vn()
    sched_stmt = (
        select(Schedule)
        .where(Schedule.class_id == class_id, Schedule.study_date == today)
        .order_by(Schedule.start_time)
    )
    day_schedules = (await db.execute(sched_stmt)).scalars().all()
    sched = _current_session(list(day_schedules), datetime.now(_VN_TZ))

    # 2. Lấy danh sách sinh viên ghi danh trong lớp
    stmt_students = (
        select(User)
        .join(ClassStudent, ClassStudent.student_id == User.id)
        .options(selectinload(User.student_profile))
        .where(
            ClassStudent.class_id == class_id,
            User.is_active == True,
            User.deleted_at.is_(None),
        )
        .order_by(User.user_code)
    )
    students = (await db.execute(stmt_students)).scalars().all()
    total_students = len(students)

    # 3. Lấy attendances cho schedule nếu có
    att_by_student: Dict[int, Attendance] = {}
    if sched:
        att_stmt = select(Attendance).where(Attendance.schedule_id == sched.id)
        attendances = (await db.execute(att_stmt)).scalars().all()
        att_by_student = {a.student_id: a for a in attendances}

    checked_in_count = 0
    absent_count = 0
    uniform_violation_count = 0
    student_items: List[StudentAttendanceLiveItem] = []

    for s in students:
        att = att_by_student.get(s.id)
        class_name = s.student_profile.class_name if s.student_profile else ""
        if att:
            is_checked = (
                att.check_in_time is not None
                or att.status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.HALF_ABSENT]
            )
            if is_checked:
                checked_in_count += 1
                if not att.has_uniform:
                    uniform_violation_count += 1
            else:
                absent_count += 1

            student_items.append(
                StudentAttendanceLiveItem(
                    attendance_id=att.id,
                    student_id=s.id,
                    student_code=s.user_code,
                    full_name=s.full_name,
                    class_name=class_name,
                    check_in_time=att.check_in_time,
                    check_out_time=att.check_out_time,
                    check_in_snapshot_url=att.check_in_snapshot_url,
                    check_out_snapshot_url=att.check_out_snapshot_url,
                    has_uniform=att.has_uniform,
                    status=att.status.value,
                    is_manual_override=att.is_manual_override,
                    source=_attendance_source(att),
                )
            )
        else:
            absent_count += 1
            student_items.append(
                StudentAttendanceLiveItem(
                    attendance_id=None,
                    student_id=s.id,
                    student_code=s.user_code,
                    full_name=s.full_name,
                    class_name=class_name,
                    check_in_time=None,
                    check_out_time=None,
                    has_uniform=True,
                    status=AttendanceStatus.ABSENT.value,
                    is_manual_override=False,
                    source="none",
                )
            )

    return LiveAttendanceResponse(
        class_id=class_obj.id,
        class_code=class_obj.class_code,
        course_name=class_obj.course_name,
        schedule_id=sched.id if sched else None,
        study_date=sched.study_date if sched else None,
        start_time=sched.start_time.strftime("%H:%M") if sched else None,
        end_time=sched.end_time.strftime("%H:%M") if sched else None,
        room_name=sched.room_name if sched else None,
        total_students=total_students,
        checked_in_count=checked_in_count,
        absent_count=absent_count,
        uniform_violation_count=uniform_violation_count,
        students=student_items,
    )


@router.get(
    "/classes/{class_id}/students/{student_id}/attendance-history",
    response_model=StudentHistoryResponse,
    summary="Xem lịch sử điểm danh của 1 sinh viên trong 1 lớp học phần",
)
async def get_student_attendance_history(
    class_id: int,
    student_id: int,
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    class_obj = (
        await db.execute(
            select(Class).options(selectinload(Class.course)).where(Class.id == class_id)
        )
    ).scalar_one_or_none()
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy lớp học phần",
        )
    if class_obj.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem dữ liệu của lớp học này",
        )

    # Sinh viên phải thuộc lớp học phần.
    cs_stmt = select(ClassStudent).where(
        ClassStudent.class_id == class_id,
        ClassStudent.student_id == student_id,
    )
    if not (await db.execute(cs_stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sinh viên không thuộc lớp học phần này",
        )
    student = await db.get(User, student_id)

    # Tất cả buổi học của lớp + điểm danh của SV (LEFT JOIN bằng tay để
    # buổi chưa điểm danh vẫn hiện dòng "chưa điểm danh").
    sched_stmt = (
        select(Schedule)
        .where(Schedule.class_id == class_id)
        .order_by(Schedule.study_date.asc(), Schedule.start_time.asc())
    )
    schedules = (await db.execute(sched_stmt)).scalars().all()
    att_stmt = select(Attendance).where(
        Attendance.student_id == student_id,
        Attendance.schedule_id.in_([s.id for s in schedules]) if schedules else False,
    )
    att_by_sched = (
        {(a.schedule_id): a for a in (await db.execute(att_stmt)).scalars().all()}
        if schedules
        else {}
    )

    items: List[StudentHistoryItem] = []
    summary = StudentHistorySummary(total_sessions=len(schedules))

    # Bulk lấy tổng điểm biến động theo từng buổi (1 query thay N+1).
    # Một buổi có thể có nhiều dòng ledger (NIGHTLY_EVAL + LEAVE_REFUND)
    # nên cộng gộp theo schedule_id để ra điểm thực trừ/cộng của buổi đó.
    delta_by_schedule: Dict[int, int] = {}
    evaluated_schedule_ids: set[int] = set()
    if schedules:
        ledger_stmt = select(PointLedger).where(
            PointLedger.student_id == student_id,
            PointLedger.schedule_id.in_([s.id for s in schedules]),
        )
        for entry in (await db.execute(ledger_stmt)).scalars().all():
            if entry.schedule_id is None:
                continue
            evaluated_schedule_ids.add(entry.schedule_id)
            delta_by_schedule[entry.schedule_id] = (
                delta_by_schedule.get(entry.schedule_id, 0) + entry.point_delta
            )

    for s in schedules:
        att = att_by_sched.get(s.id)
        st_str = s.start_time.strftime("%H:%M") if hasattr(s.start_time, "strftime") else str(s.start_time)
        et_str = s.end_time.strftime("%H:%M") if hasattr(s.end_time, "strftime") else str(s.end_time)
        point_delta = (
            delta_by_schedule.get(s.id) if s.id in evaluated_schedule_ids else None
        )
        if point_delta is not None and point_delta < 0:
            summary.total_deducted += abs(point_delta)
        if att:
            status_val = att.status.value if isinstance(att.status, AttendanceStatus) else str(att.status)
            key = status_val.lower()
            if key == "present":
                summary.present += 1
            elif key == "late":
                summary.late += 1
            elif key == "half_absent":
                summary.half_absent += 1
            elif key == "excused":
                summary.excused += 1
            else:
                summary.absent += 1
            items.append(
                StudentHistoryItem(
                    schedule_id=s.id,
                    study_date=s.study_date,
                    start_time=st_str,
                    end_time=et_str,
                    session_order=s.session_order,
                    room_name=s.room_name,
                    attendance_id=att.id,
                    check_in_time=att.check_in_time,
                    check_out_time=att.check_out_time,
                    check_in_snapshot_url=att.check_in_snapshot_url,
                    check_out_snapshot_url=att.check_out_snapshot_url,
                    has_uniform=att.has_uniform,
                    status=status_val,
                    is_manual_override=att.is_manual_override,
                    source=_attendance_source(att),
                    note=att.note,
                    point_delta=point_delta,
                )
            )
        else:
            summary.absent += 1
            items.append(
                StudentHistoryItem(
                    schedule_id=s.id,
                    study_date=s.study_date,
                    start_time=st_str,
                    end_time=et_str,
                    session_order=s.session_order,
                    room_name=s.room_name,
                    point_delta=point_delta,
                )
            )

    return StudentHistoryResponse(
        class_id=class_obj.id,
        class_code=class_obj.class_code,
        course_name=class_obj.course_name,
        student_id=student_id,
        student_code=student.user_code if student else "",
        full_name=student.full_name if student else "",
        summary=summary,
        items=items,
    )


@router.put(
    "/attendance/{attendance_id}/manual-override",
    response_model=AttendanceDetailResponse,
    summary="Giảng viên cập nhật điểm danh thủ công",
)
async def manual_override_attendance(
    attendance_id: int,
    body: ManualOverrideRequest,
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    att = None
    if attendance_id > 0:
        stmt = (
            select(Attendance)
            .options(selectinload(Attendance.schedule).selectinload(Schedule.clazz))
            .where(Attendance.id == attendance_id)
        )
        result = await db.execute(stmt)
        att = result.scalar_one_or_none()

    if not att:
        if body.schedule_id and body.student_id:
            # Check if schedule exists and belongs to current teacher
            sched_stmt = (
                select(Schedule)
                .options(selectinload(Schedule.clazz))
                .where(Schedule.id == body.schedule_id)
            )
            sched_res = await db.execute(sched_stmt)
            sched = sched_res.scalar_one_or_none()
            if not sched or not sched.clazz or sched.clazz.teacher_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền can thiệp điểm danh của buổi học này",
                )

            # Check if attendance already exists for this student in this schedule
            exist_stmt = select(Attendance).where(
                Attendance.schedule_id == body.schedule_id,
                Attendance.student_id == body.student_id,
            )
            att = (await db.execute(exist_stmt)).scalar_one_or_none()
            if not att:
                att = Attendance(
                    schedule_id=body.schedule_id,
                    student_id=body.student_id,
                    has_uniform=True,
                    status=body.status,
                    note=body.note or "",
                    is_manual_override=True,
                    updated_by=current_user.id,
                )
                db.add(att)
                await db.commit()
                await db.refresh(att)
                return att
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy bản ghi điểm danh",
            )

    if not att.schedule or not att.schedule.clazz or att.schedule.clazz.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền can thiệp điểm danh của lớp này",
        )

    att.status = body.status
    att.note = body.note or ""
    att.is_manual_override = True
    att.updated_by = current_user.id

    await db.commit()
    await db.refresh(att)
    return att


@router.get(
    "/classes/{class_id}/exam-ban-report",
    summary="Xem dữ liệu báo cáo cấm thi của lớp học phần",
)
async def get_class_exam_ban_report(
    class_id: int,
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    class_obj = (
        await db.execute(
            select(Class).options(selectinload(Class.course)).where(Class.id == class_id)
        )
    ).scalar_one_or_none()
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy lớp học phần",
        )

    if class_obj.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem báo cáo của lớp học này",
        )

    report_data = await calculate_class_exam_ban(db, class_id)
    if not report_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy dữ liệu lớp học",
        )
    return report_data


@router.get(
    "/classes/{class_id}/export-exam-ban-excel",
    summary="Xuất file Excel danh sách cấm thi của lớp học phần",
)
async def export_class_exam_ban_excel(
    class_id: int,
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    class_obj = await get_or_404(db, Class, class_id, detail="Không tìm thấy lớp học phần")

    if class_obj.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xuất báo cáo của lớp học này",
        )

    report_data = await calculate_class_exam_ban(db, class_id)
    if not report_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy dữ liệu lớp học",
        )

    title = f"DANH SÁCH CẤM THI LỚP {class_obj.class_code}"
    subtitle = f"Môn học: {class_obj.course_name} - Học kỳ: {class_obj.semester}"
    excel_bytes = generate_excel_exam_ban(report_data.get("students", []), title=title, subtitle=subtitle)

    filename = f"cam_thi_{class_obj.class_code}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

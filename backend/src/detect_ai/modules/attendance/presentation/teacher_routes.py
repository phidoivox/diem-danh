from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.timeutil import VN_TZ as _VN_TZ
from detect_ai.shared.kernel.timeutil import today_vn as _today_vn
from detect_ai.modules.academic.public import (
    AdministrativeClass,
    Class,
    ClassStudent,
    Schedule,
)
from ..infrastructure.models import Attendance, AttendanceStatus
from detect_ai.modules.evaluation.public import PointLedger
from detect_ai.modules.reporting.public import (
    build_class_conduct_rows,
    calculate_class_exam_ban,
    generate_excel_conduct,
    generate_excel_exam_ban,
    parse_month_param,
    summarize_conduct,
)
from detect_ai.modules.identity.public import User
from detect_ai.modules.identity.public import StudentProfile
from detect_ai.modules.identity.public import require_teacher
from detect_ai.shared.kernel.helpers import get_or_404

router = APIRouter(
    prefix="/api/v1/teacher",
    tags=["teacher"],
    dependencies=[Depends(require_teacher)],
)


# =====================================================================
# SCHEMAS
# =====================================================================


from detect_ai.modules.attendance.presentation.deps import in_window


def _current_session(
    schedules: List[Schedule], now: Optional[datetime] = None
) -> Optional[Schedule]:
    """Buổi đang diễn ra (start <= now < end). Ngoài giờ -> None."""
    if not schedules:
        return None
    ordered = sorted(schedules, key=lambda s: (s.start_time, s.end_time, s.id))
    current = (now or datetime.now(_VN_TZ)).time().replace(tzinfo=None)
    for s in ordered:
        if in_window(s.start_time, s.end_time, current):
            return s
    return None


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
    has_uniform: Optional[bool] = None


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
    from detect_ai.modules.reporting.public import build_student_history

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

    data = await build_student_history(db, class_id, student_id)
    summary = StudentHistorySummary(**data["summary"])
    items = [StudentHistoryItem(**it) for it in data["items"]]
    return StudentHistoryResponse(
        class_id=data["class_id"],
        class_code=data["class_code"],
        course_name=data["course_name"],
        student_id=data["student_id"],
        student_code=data["student_code"],
        full_name=data["full_name"],
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
    if body.has_uniform is not None:
        att.has_uniform = body.has_uniform
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


class SendWarningsRequest(BaseModel):
    only: str = "all"
    dry_run: bool = False


class ClassConductStudent(BaseModel):
    student_id: int
    student_code: str
    full_name: str
    class_name: str = ""
    total_point: int
    is_officer: bool = False
    conduct_rank: str
    class_delta: int
    class_entries: int


class ClassConductResponse(BaseModel):
    class_id: int
    class_code: str
    course_name: str
    evaluated_sessions: int
    total_sessions: int
    summary: dict
    students: List[ClassConductStudent]


async def _load_conduct_rows(db: AsyncSession, class_id: int, ym: tuple[int, int] | None):
    """Load students + schedules (lọc tháng) + ledger -> (class_obj, schedules, rows)."""
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
    students = (
        await db.execute(
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
    ).scalars().all()
    sched_stmt = select(Schedule).where(Schedule.class_id == class_id)
    if ym is not None:
        sched_stmt = sched_stmt.where(
            extract("year", Schedule.study_date) == ym[0],
            extract("month", Schedule.study_date) == ym[1],
        )
    sched_stmt = sched_stmt.order_by(Schedule.study_date, Schedule.start_time)
    schedules = ((await db.execute(sched_stmt)).scalars().all())
    sched_ids = [s.id for s in schedules]
    ledger: list = []
    if sched_ids:
        ledger = (
            (
                await db.execute(
                    select(PointLedger).where(PointLedger.schedule_id.in_(sched_ids))
                )
            )
            .scalars()
            .all()
        )
    rows = build_class_conduct_rows(list(students), list(schedules), list(ledger))
    return class_obj, schedules, rows


@router.get(
    "/classes/{class_id}/conduct-points",
    response_model=ClassConductResponse,
    summary="Bảng điểm rèn luyện lớp mình: global + delta trong lớp + rank",
)
async def get_class_conduct_points(
    class_id: int,
    month: Optional[str] = None,
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        ym = parse_month_param(month)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    class_obj, schedules, rows = await _load_conduct_rows(db, class_id, ym)
    if class_obj.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem dữ liệu của lớp học này",
        )
    evaluated = rows[0]["evaluated_sessions"] if rows else 0
    return ClassConductResponse(
        class_id=class_obj.id,
        class_code=class_obj.class_code,
        course_name=class_obj.course_name,
        evaluated_sessions=evaluated,
        total_sessions=len(schedules),
        summary=summarize_conduct(rows),
        students=[ClassConductStudent(**{k: r[k] for k in ClassConductStudent.model_fields}) for r in rows],
    )


@router.get(
    "/classes/{class_id}/export-conduct-excel",
    summary="Xuất file Excel điểm rèn luyện lớp mình (kèm lọc tháng)",
)
async def export_class_conduct_excel(
    class_id: int,
    month: Optional[str] = None,
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        ym = parse_month_param(month)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    class_obj, schedules, rows = await _load_conduct_rows(db, class_id, ym)
    if class_obj.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xuất báo cáo của lớp học này",
        )
    label = f"tháng {month}" if month else "toàn kỳ"
    title = f"ĐIỂM RÈN LUYỆN LỚP {class_obj.class_code} ({label})"
    subtitle = f"Môn học: {class_obj.course_name} - Đã chấm {rows[0]['evaluated_sessions'] if rows else 0}/{len(schedules)} buổi"
    excel_bytes = generate_excel_conduct(rows, title=title, subtitle=subtitle)
    filename = f"diem_ren_luyen_{class_obj.class_code}{('_' + month) if month else ''}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/classes/{class_id}/send-exam-warnings",
    summary="GV gửi mail cảnh báo/cấm thi lớp mình",
)
async def send_class_exam_warnings_teacher(
    class_id: int,
    body: SendWarningsRequest,
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    class_obj = await get_or_404(db, Class, class_id, detail="Không tìm thấy lớp học phần")
    if class_obj.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền gửi mail lớp này",
        )
    from detect_ai.shared.notifications import service as notif_service

    only = body.only if body.only in ("all", "warning", "banned") else "all"
    return await notif_service.send_class_exam_warnings(db, class_id, only, body.dry_run)


class OfficerUpdateRequest(BaseModel):
    is_officer: bool


@router.get(
    "/homeroom-classes",
    summary="Lớp SH do GV làm chủ nhiệm",
)
async def get_homeroom_classes(
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(AdministrativeClass).where(
                AdministrativeClass.homeroom_teacher_id == current_user.id
            )
        )
    ).scalars().all()
    return [
        {"id": r.id, "class_code": r.class_code, "faculty": r.faculty}
        for r in rows
    ]


@router.get(
    "/homeroom-classes/{admin_class_id}/students",
    summary="GVCN xem SV lớp SH mình chủ nhiệm (kèm cờ cán sự)",
)
async def get_homeroom_students(
    admin_class_id: int,
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    ac = await get_or_404(db, AdministrativeClass, admin_class_id, detail="Không tìm thấy lớp sinh hoạt")
    if ac.homeroom_teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không phải GVCN lớp này",
        )
    students = (
        await db.execute(
            select(User)
            .join(StudentProfile, StudentProfile.user_id == User.id)
            .options(selectinload(User.student_profile))
            .where(
                StudentProfile.admin_class_id == admin_class_id,
                User.deleted_at.is_(None),
            )
            .order_by(User.user_code)
        )
    ).scalars().all()
    return [
        {
            "id": stu.id,
            "user_code": stu.user_code,
            "full_name": stu.full_name,
            "total_point": stu.student_profile.total_point if stu.student_profile else 100,
            "is_officer": bool(stu.student_profile.is_officer) if stu.student_profile else False,
        }
        for stu in students
    ]


@router.put(
    "/homeroom-classes/{admin_class_id}/students/{student_id}/officer",
    summary="GVCN gán/bỏ cờ ban cán sự cho SV lớp mình",
)
async def set_homeroom_officer(
    admin_class_id: int,
    student_id: int,
    body: OfficerUpdateRequest,
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    ac = await get_or_404(db, AdministrativeClass, admin_class_id, detail="Không tìm thấy lớp sinh hoạt")
    if ac.homeroom_teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không phải GVCN lớp này",
        )
    prof_stmt = select(StudentProfile).where(
        StudentProfile.user_id == student_id,
        StudentProfile.admin_class_id == admin_class_id,
    )
    profile = (await db.execute(prof_stmt)).scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sinh viên không thuộc lớp sinh hoạt này",
        )
    profile.is_officer = body.is_officer
    await db.commit()
    return {"ok": True, "student_id": student_id, "is_officer": body.is_officer}

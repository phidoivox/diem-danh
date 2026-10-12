from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.helpers import get_or_404
from sqlalchemy import extract, select
from sqlalchemy.orm import selectinload
from typing import List
from detect_ai.modules.academic.public import Class, ClassStudent, Schedule
from detect_ai.modules.evaluation.public import PointLedger
from detect_ai.modules.identity.public import User
from detect_ai.modules.reporting.application.conduct import (
    build_class_conduct_rows,
    generate_excel_conduct,
    parse_month_param,
    summarize_conduct,
)
from ..application.build import (
    calculate_all_classes_exam_ban,
    calculate_class_exam_ban,
    generate_excel_exam_ban,
)
from detect_ai.modules.identity.public import require_role

router = APIRouter(
    prefix="/api/v1/admin/reports",
    tags=["admin-reports"],
    dependencies=[Depends(require_role("ADMIN"))],
)


@router.get(
    "/classes/{class_id}/exam-ban-report",
    summary="Admin xem dữ liệu báo cáo cấm thi của một lớp học phần",
)
async def get_class_exam_ban_report(
    class_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    report_data = await calculate_class_exam_ban(db, class_id)
    if not report_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy dữ liệu lớp học",
        )
    return report_data


@router.get(
    "/classes/{class_id}/export-exam-ban-excel",
    summary="Admin xuất file Excel danh sách cấm thi của một lớp học phần",
)
async def export_class_exam_ban_excel(
    class_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    class_obj = await get_or_404(db, Class, class_id, detail="Không tìm thấy lớp học phần")
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


@router.get(
    "/export-exam-ban-all-excel",
    summary="Admin xuất file Excel danh sách cấm thi của toàn trường",
)
async def export_exam_ban_all_excel(
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    all_student_rows = await calculate_all_classes_exam_ban(db)
    title = "DANH SÁCH CẤM THI TOÀN TRƯỜNG"
    subtitle = "Tổng hợp danh sách cấm thi tất cả các lớp học phần"

    excel_bytes = generate_excel_exam_ban(all_student_rows, title=title, subtitle=subtitle)
    filename = "danh_sach_cam_thi_toan_truong.xlsx"

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class SendWarningsRequest(BaseModel):
    only: str = "all"
    dry_run: bool = False


class AdminConductStudent(BaseModel):
    student_id: int
    student_code: str
    full_name: str
    class_name: str = ""
    total_point: int
    is_officer: bool = False
    conduct_rank: str
    class_delta: int
    class_entries: int


class AdminConductResponse(BaseModel):
    class_id: int
    class_code: str
    course_name: str
    evaluated_sessions: int
    total_sessions: int
    summary: dict
    students: List[AdminConductStudent]


async def _load_admin_conduct_rows(db, class_id: int, ym):
    class_obj = await get_or_404(db, Class, class_id, detail="Không tìm thấy lớp học phần")
    students = (
        (
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
        )
        .scalars()
        .all()
    )
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
    summary="Admin xem bảng điểm rèn luyện 1 lớp học phần",
)
async def get_admin_class_conduct(
    class_id: int,
    month: str | None = None,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    try:
        ym = parse_month_param(month)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    class_obj, schedules, rows = await _load_admin_conduct_rows(db, class_id, ym)
    evaluated = rows[0]["evaluated_sessions"] if rows else 0
    return AdminConductResponse(
        class_id=class_obj.id,
        class_code=class_obj.class_code,
        course_name=class_obj.course_name,
        evaluated_sessions=evaluated,
        total_sessions=len(schedules),
        summary=summarize_conduct(rows),
        students=[AdminConductStudent(**{k: r[k] for k in AdminConductStudent.model_fields}) for r in rows],
    )


@router.get(
    "/classes/{class_id}/export-conduct-excel",
    summary="Admin xuất file Excel điểm rèn luyện 1 lớp (kèm lọc tháng)",
)
async def export_admin_class_conduct_excel(
    class_id: int,
    month: str | None = None,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    try:
        ym = parse_month_param(month)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    class_obj, schedules, rows = await _load_admin_conduct_rows(db, class_id, ym)
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


@router.get(
    "/classes/{class_id}/students/{student_id}/attendance-history",
    summary="Admin xem lịch sử điểm danh 1 SV trong 1 lớp học phần",
)
async def get_admin_student_history(
    class_id: int,
    student_id: int,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    from detect_ai.modules.reporting.public import build_student_history

    return await build_student_history(db, class_id, student_id)


@router.post("/classes/{class_id}/send-exam-warnings")
async def send_class_exam_warnings_manual(
    class_id: int,
    body: SendWarningsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Admin gửi bù mail cảnh báo/cấm thi 1 lớp."""
    from detect_ai.shared.notifications import service as notif_service

    only = body.only if body.only in ("all", "warning", "banned") else "all"
    return await notif_service.send_class_exam_warnings(db, class_id, only, body.dry_run)


class TestEmailRequest(BaseModel):
    to: str


@router.post("/notifications/test")
async def send_test_email(
    body: TestEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    """Admin gửi mail test verify SMTP (cấu hình đọc từ database)."""
    from detect_ai.shared.notifications import mailer

    res = await mailer.send(
        body.to, "[Test] Hệ thống điểm danh",
        "<p>SMTP hoạt động bình thường.</p>", "SMTP hoạt động bình thường.",
        db,
    )
    return res

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.helpers import get_or_404
from detect_ai.modules.academic.public import Class
from detect_ai.modules.identity.public import User
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

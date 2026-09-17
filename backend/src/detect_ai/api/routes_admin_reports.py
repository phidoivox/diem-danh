from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_db
from ..models.user import User
from ..services.report_service import (
    calculate_all_classes_exam_ban,
    generate_excel_exam_ban,
)
from .deps_auth import require_role

router = APIRouter(
    prefix="/api/v1/admin/reports",
    tags=["admin-reports"],
    dependencies=[Depends(require_role("ADMIN"))],
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

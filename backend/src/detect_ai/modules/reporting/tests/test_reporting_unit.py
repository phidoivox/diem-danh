from __future__ import annotations

import io
import openpyxl

from detect_ai.modules.reporting.public import (
    calculate_all_classes_exam_ban,
    calculate_class_exam_ban,
    generate_excel_exam_ban,
)
from detect_ai.modules.reporting.application.build import (
    EXAM_BAN_HEADERS,
    calculate_all_classes_exam_ban as app_all,
    calculate_class_exam_ban as app_class,
    generate_excel_exam_ban as app_excel,
)
from detect_ai.modules.reporting.presentation.routes import router as admin_reports_router
from detect_ai.modules.reporting.presentation.portal_routes import router as student_portal_router
from detect_ai.services import report_service
from detect_ai.api import routes_admin_reports, routes_student_portal


def test_public_reexports():
    assert calculate_class_exam_ban is app_class
    assert calculate_all_classes_exam_ban is app_all
    assert generate_excel_exam_ban is app_excel


def test_generate_excel_exam_ban():
    data = [
        {
            "student_id": 1,
            "student_code": "SV001",
            "full_name": "Nguyen Van A",
            "class_name": "D20CNTT1",
            "course_name": "Python",
            "absent_count": 3,
            "half_absent_count": 1,
            "rate_semester": 23.3,
            "status_label": "BỊ CẤM THI",
            "is_banned": True,
            "is_warning": False,
        },
        {
            "student_id": 2,
            "student_code": "SV002",
            "full_name": "Tran Thi B",
            "class_name": "D20CNTT1",
            "course_name": "Python",
            "absent_count": 1,
            "half_absent_count": 0,
            "rate_semester": 6.7,
            "status_label": "ĐỦ ĐIỀU KIỆN",
            "is_banned": False,
            "is_warning": False,
        },
    ]
    raw_bytes = generate_excel_exam_ban(data, title="BÁO CÁO CẤM THI", subtitle="Lớp D20CNTT1")
    assert isinstance(raw_bytes, bytes)
    assert len(raw_bytes) > 0

    wb = openpyxl.load_workbook(io.BytesIO(raw_bytes))
    ws = wb.active
    assert ws.title == "Danh sách cấm thi"

    # Row 1: Title
    assert ws["A1"].value == "BÁO CÁO CẤM THI"
    # Row 2: Subtitle
    assert ws["A2"].value == "Lớp D20CNTT1"
    # Row 4: Headers
    headers = [ws.cell(row=4, column=col).value for col in range(1, len(EXAM_BAN_HEADERS) + 1)]
    assert headers == EXAM_BAN_HEADERS

    # Row 5: First student
    assert ws.cell(row=5, column=2).value == "SV001"
    assert ws.cell(row=5, column=3).value == "Nguyen Van A"
    assert ws.cell(row=5, column=9).value == "BỊ CẤM THI"

    # Row 6: Second student
    assert ws.cell(row=6, column=2).value == "SV002"
    assert ws.cell(row=6, column=9).value == "ĐỦ ĐIỀU KIỆN"


def test_routers_structure():
    assert admin_reports_router.prefix == "/api/v1/admin/reports"
    admin_paths = [r.path for r in admin_reports_router.routes]
    assert "/api/v1/admin/reports/export-exam-ban-all-excel" in admin_paths

    assert student_portal_router.prefix == "/api/v1/student"
    portal_paths = [r.path for r in student_portal_router.routes]
    assert "/api/v1/student/schedule" in portal_paths
    assert "/api/v1/student/attendance" in portal_paths
    assert "/api/v1/student/conduct-ledger" in portal_paths


def test_shims_completeness():
    assert report_service.calculate_class_exam_ban is app_class
    assert report_service.calculate_all_classes_exam_ban is app_all
    assert report_service.generate_excel_exam_ban is app_excel
    assert routes_admin_reports.router is admin_reports_router
    assert routes_student_portal.router is student_portal_router

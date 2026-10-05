from __future__ import annotations

import pytest
from detect_ai.modules.attendance.infrastructure.models import Attendance, AttendanceStatus
from detect_ai.modules.attendance.presentation.teacher_routes import (
    router,
    _current_session,
    get_teacher_classes,
    get_class_live_attendance,
    get_student_attendance_history,
    manual_override_attendance,
    get_class_exam_ban_report,
    export_class_exam_ban_excel,
)


def test_models_exist():
    assert Attendance.__tablename__ == "attendance"
    assert AttendanceStatus.PRESENT.value == "PRESENT"
    assert AttendanceStatus.ABSENT.value == "ABSENT"


def test_shims_completeness():
    from detect_ai.models.attendance_v2 import (
        Attendance as ShimAttendance,
        AttendanceStatus as ShimAttendanceStatus,
    )
    from detect_ai.api.routes_teacher import (
        router as shim_router,
        _current_session as shim_current_session,
    )

    assert ShimAttendance is Attendance
    assert ShimAttendanceStatus is AttendanceStatus
    assert shim_router is router
    assert shim_current_session is _current_session


def test_main_app_openapi_teacher_routes():
    from detect_ai.main import app

    openapi = app.openapi()
    paths = openapi["paths"]

    expected_routes = {
        "/api/v1/teacher/classes": {"get"},
        "/api/v1/teacher/classes/{class_id}/live-attendance": {"get"},
        "/api/v1/teacher/classes/{class_id}/students/{student_id}/attendance-history": {"get"},
        "/api/v1/teacher/attendance/{attendance_id}/manual-override": {"put"},
        "/api/v1/teacher/classes/{class_id}/exam-ban-report": {"get"},
        "/api/v1/teacher/classes/{class_id}/export-exam-ban-excel": {"get"},
    }

    for route, methods in expected_routes.items():
        assert route in paths, f"Missing route {route} in openapi"
        registered_methods = set(paths[route].keys())
        assert methods.issubset(registered_methods), (
            f"Route {route} missing methods: {methods - registered_methods}"
        )

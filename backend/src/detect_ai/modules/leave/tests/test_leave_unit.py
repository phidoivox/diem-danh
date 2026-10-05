from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from detect_ai.modules.leave.domain.request import LeaveRequestEntity, LeaveStatus
from detect_ai.modules.leave.public import LeaveStatus as PublicLeaveStatus, is_excused


def test_domain_entity_creation():
    req = LeaveRequestEntity(
        id=1,
        schedule_id=10,
        student_id=20,
        reason="Bệnh có giấy khám",
    )
    assert req.id == 1
    assert req.schedule_id == 10
    assert req.student_id == 20
    assert req.reason == "Bệnh có giấy khám"
    assert req.status == LeaveStatus.PENDING
    assert req.proof_image is None
    assert req.teacher_feedback is None


def test_domain_enum_values():
    assert LeaveStatus.PENDING == "PENDING"
    assert LeaveStatus.APPROVED == "APPROVED"
    assert LeaveStatus.REJECTED == "REJECTED"
    assert PublicLeaveStatus is LeaveStatus


@pytest.mark.asyncio
async def test_is_excused_true():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = 1
    mock_session.execute.return_value = mock_result

    res = await is_excused(mock_session, schedule_id=10, student_id=20)
    assert res is True
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_is_excused_false():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    res = await is_excused(mock_session, schedule_id=10, student_id=20)
    assert res is False
    mock_session.execute.assert_called_once()


def test_shims_completeness():
    from detect_ai.models.leave_request import LeaveRequest as ShimLeaveRequest, LeaveStatus as ShimLeaveStatus
    from detect_ai.api.routes_leave_requests import (
        router as shim_router,
        submit_leave_request,
        get_student_leave_requests,
        get_teacher_leave_requests,
        review_leave_request,
        format_leave_request,
        LeaveRequestResponse,
        LeaveRequestPage,
        ReviewLeaveRequestSchema,
    )
    from detect_ai.application.use_cases.review_leave import review_leave as shim_review_leave
    from detect_ai.modules.leave.infrastructure.models import LeaveRequest, LeaveStatus
    from detect_ai.modules.leave.presentation.routes import router
    from detect_ai.modules.leave.application.review import review_leave

    assert ShimLeaveRequest is LeaveRequest
    assert ShimLeaveStatus is LeaveStatus
    assert shim_router is router
    assert shim_review_leave is review_leave
    assert callable(submit_leave_request)
    assert callable(get_student_leave_requests)
    assert callable(get_teacher_leave_requests)
    assert callable(review_leave_request)
    assert callable(format_leave_request)


def test_main_app_openapi_leave_routes():
    from detect_ai.main import app

    openapi = app.openapi()
    paths = openapi.get("paths", {})

    assert "/api/v1/student/leave-requests" in paths
    student_methods = set(paths["api/v1/student/leave-requests" if "api/v1/student/leave-requests" in paths else "/api/v1/student/leave-requests"].keys())
    assert "post" in student_methods
    assert "get" in student_methods

    assert "/api/v1/teacher/leave-requests" in paths
    teacher_methods = set(paths["/api/v1/teacher/leave-requests"].keys())
    assert "get" in teacher_methods

    assert "/api/v1/teacher/leave-requests/{id}/review" in paths
    review_methods = set(paths["/api/v1/teacher/leave-requests/{id}/review"].keys())
    assert "post" in review_methods


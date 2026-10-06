from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from detect_ai.modules.academic.infrastructure.models import Class, ClassStudent, Schedule
from detect_ai.modules.academic.public import get_class, get_schedule


@pytest.mark.asyncio
async def test_public_get_schedule():
    mock_session = AsyncMock()
    mock_schedule = MagicMock()
    mock_session.get.return_value = mock_schedule

    res = await get_schedule(mock_session, 10)
    assert res is mock_schedule
    mock_session.get.assert_called_once_with(Schedule, 10)


@pytest.mark.asyncio
async def test_public_get_class():
    mock_session = AsyncMock()
    mock_class = MagicMock()
    mock_session.get.return_value = mock_class

    res = await get_class(mock_session, 1)
    assert res is mock_class
    mock_session.get.assert_called_once_with(Class, 1)


def test_shims_completeness():
    from detect_ai.modules.academic.infrastructure.models import (
        Class as ShimClass,
        ClassStudent as ShimClassStudent,
        Schedule as ShimSchedule,
    )
    from detect_ai.modules.academic.presentation.routes import (
        ClassCreateRequest,
        ClassPage,
        ClassUpdateRequest,
        EnrollStudentRequest,
        ScheduleCreateRequest,
        ScheduleResponse,
        ScheduleUpdateRequest,
        StudentInClassResponse,
        check_room_conflict,
        create_class,
        create_schedule,
        delete_class,
        delete_schedule,
        enroll_student,
        list_class_students,
        list_classes,
        list_schedules,
        remove_student_from_class,
        router as shim_router,
        update_class,
        update_schedule,
    )
    from detect_ai.modules.academic.presentation.routes import router

    assert ShimClass is Class
    assert ShimClassStudent is ClassStudent
    assert ShimSchedule is Schedule
    assert shim_router is router
    assert callable(create_class)
    assert callable(list_classes)
    assert callable(update_class)
    assert callable(delete_class)
    assert callable(enroll_student)
    assert callable(remove_student_from_class)
    assert callable(list_class_students)
    assert callable(create_schedule)
    assert callable(list_schedules)
    assert callable(update_schedule)
    assert callable(delete_schedule)
    assert callable(check_room_conflict)
    assert issubclass(ClassPage, object)
    assert issubclass(ClassCreateRequest, object)
    assert issubclass(ClassUpdateRequest, object)
    assert issubclass(StudentInClassResponse, object)
    assert issubclass(EnrollStudentRequest, object)
    assert issubclass(ScheduleResponse, object)
    assert issubclass(ScheduleCreateRequest, object)
    assert issubclass(ScheduleUpdateRequest, object)


def test_main_app_openapi_academic_routes():
    from detect_ai.main import app

    openapi = app.openapi()
    paths = openapi["paths"]

    expected_routes = {
        "/api/v1/admin/academic/classes": {"get", "post"},
        "/api/v1/admin/academic/classes/{class_id}": {"put", "delete"},
        "/api/v1/admin/academic/classes/{class_id}/students": {"get", "post"},
        "/api/v1/admin/academic/classes/{class_id}/students/{student_id}": {"delete"},
        "/api/v1/admin/academic/schedules": {"get", "post"},
        "/api/v1/admin/academic/schedules/{schedule_id}": {"put", "delete"},
    }

    for route, methods in expected_routes.items():
        assert route in paths, f"Missing route {route} in openapi"
        registered_methods = set(paths[route].keys())
        assert methods.issubset(registered_methods), (
            f"Route {route} missing methods: {methods - registered_methods}"
        )

from __future__ import annotations

from datetime import datetime

from detect_ai.modules.evaluation.domain.exam_ban import converted_absent
from detect_ai.modules.evaluation.domain.policy import decide_attendance
from detect_ai.modules.evaluation.public import (
    decide_attendance as pub_decide,
    run_nightly_evaluation as pub_run,
)


POINTS = {
    "PRESENT": 2,
    "LATE": -1,
    "HALF_ABSENT": -2,
    "ABSENT": -5,
    "EXCUSED": 0,
    "UNIFORM_VIOLATION": -2,
}


def test_public_reexports():
    assert pub_decide is decide_attendance
    assert callable(pub_run)


def test_exam_ban_converted_absent():
    assert converted_absent(2, 1) == 2.5
    assert converted_absent(0, 0) == 0.0
    assert converted_absent(3, 0) == 3.0


def test_decide_attendance_approved_leave():
    status, delta = decide_attendance(
        check_in=None,
        check_out=None,
        start_dt=datetime(2026, 10, 5, 8, 0),
        late_tol=15,
        require_checkout=False,
        has_uniform=True,
        is_override=False,
        override_status=None,
        is_approved=True,
        points=POINTS,
    )
    assert status == "EXCUSED"
    assert delta == 0


def test_decide_attendance_on_time_with_uniform():
    status, delta = decide_attendance(
        check_in=datetime(2026, 10, 5, 8, 5),
        check_out=datetime(2026, 10, 5, 10, 0),
        start_dt=datetime(2026, 10, 5, 8, 0),
        late_tol=15,
        require_checkout=True,
        has_uniform=True,
        is_override=False,
        override_status=None,
        is_approved=False,
        points=POINTS,
    )
    assert status == "PRESENT"
    assert delta == 2


def test_decide_attendance_late_and_no_uniform():
    status, delta = decide_attendance(
        check_in=datetime(2026, 10, 5, 8, 20),
        check_out=datetime(2026, 10, 5, 10, 0),
        start_dt=datetime(2026, 10, 5, 8, 0),
        late_tol=15,
        require_checkout=False,
        has_uniform=False,
        is_override=False,
        override_status=None,
        is_approved=False,
        points=POINTS,
    )
    assert status == "LATE"
    assert delta == -1 + (-2)

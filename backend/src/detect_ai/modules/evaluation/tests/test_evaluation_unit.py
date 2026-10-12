from __future__ import annotations

from datetime import datetime

from detect_ai.modules.evaluation.domain.conduct_rank import classify_conduct
from detect_ai.modules.evaluation.domain.exam_ban import converted_absent
from detect_ai.modules.evaluation.domain.policy import decide_attendance
from detect_ai.modules.evaluation.public import (
    classify_conduct as pub_classify,
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
    assert pub_classify is classify_conduct
    assert callable(pub_run)


def test_conduct_rank_boundaries():
    cases = [
        (100, "Tốt"),
        (90, "Tốt"),
        (89, "Tốt"),
        (80, "Tốt"),
        (79, "Khá"),
        (65, "Khá"),
        (64, "Trung bình"),
        (50, "Trung bình"),
        (49, "Yếu"),
        (35, "Yếu"),
        (34, "Kém"),
        (0, "Kém"),
    ]
    for point, expected in cases:
        assert classify_conduct(point) == expected


def test_conduct_rank_coerce_and_clamp():
    assert classify_conduct(None) == "Tốt"
    assert classify_conduct(101) == "Tốt"
    assert classify_conduct(-1) == "Kém"


def test_conduct_rank_officer_cap():
    # SV thường 100 vẫn chỉ Tốt; cán sự 90+ mới Xuất sắc.
    assert classify_conduct(100) == "Tốt"
    assert classify_conduct(95) == "Tốt"
    assert classify_conduct(100, True) == "Xuất sắc"
    assert classify_conduct(90, True) == "Xuất sắc"
    assert classify_conduct(89, True) == "Tốt"
    assert classify_conduct(40) == "Yếu"
    assert classify_conduct(40, True) == "Yếu"


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

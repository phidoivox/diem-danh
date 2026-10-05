from detect_ai.modules.attendance.presentation.deps import adaptive_feedback


def test_adaptive_feedback_slow_frame_throttles():
    nxt, w = adaptive_feedback(450, 480, 900.0)
    assert nxt == 600
    assert w == 416


def test_adaptive_feedback_fast_frame_keeps_base():
    nxt, w = adaptive_feedback(450, 480, 100.0)
    assert (nxt, w) == (450, 480)

from datetime import datetime, time
from types import SimpleNamespace

from detect_ai.api.routes_teacher import _current_session


def _make(start, end, sid=1):
    return SimpleNamespace(id=sid, start_time=start, end_time=end)


def test_current_session_only_during_class():
    sched = _make(time(13, 0), time(17, 0))
    assert _current_session([sched], datetime(2026, 10, 4, 14, 0)) is sched
    # Ngoài giờ -> None (kiosk đóng, "Hôm nay không có tiết")
    assert _current_session([sched], datetime(2026, 10, 4, 12, 0)) is None
    assert _current_session([sched], datetime(2026, 10, 4, 18, 0)) is None
    assert _current_session([], datetime(2026, 10, 4, 14, 0)) is None


def test_current_session_two_sessions_picks_right_one():
    morning = _make(time(7, 30), time(11, 30), sid=1)
    afternoon = _make(time(13, 0), time(17, 0), sid=2)
    assert _current_session([morning, afternoon], datetime(2026, 10, 4, 8, 0)) is morning
    assert _current_session([morning, afternoon], datetime(2026, 10, 4, 14, 0)) is afternoon
    # Ngoài giờ (giữa 2 buổi, sau buổi cuối) -> None
    assert _current_session([morning, afternoon], datetime(2026, 10, 4, 12, 0)) is None
    assert _current_session([morning, afternoon], datetime(2026, 10, 4, 18, 0)) is None

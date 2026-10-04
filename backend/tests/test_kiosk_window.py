from datetime import date, datetime, time
from types import SimpleNamespace

from detect_ai.api.deps_kiosk import in_session_window


def _sched(start, end, study_date=None):
    today = study_date or date(2026, 10, 4)
    return SimpleNamespace(id=1, start_time=start, end_time=end, study_date=today)


def test_in_window_during():
    s = _sched(time(13, 0), time(17, 0))
    assert in_session_window(s, datetime(2026, 10, 4, 14, 0)) is True


def test_in_window_closed_outside():
    s = _sched(time(13, 0), time(17, 0))
    assert in_session_window(s, datetime(2026, 10, 4, 12, 0)) is False
    assert in_session_window(s, datetime(2026, 10, 4, 18, 0)) is False

from __future__ import annotations

from .application.checkin import record_checkin
from .application.commit import MIN_CHECKOUT_GAP_MINUTES, commit_decisions
from .infrastructure.models import Attendance, AttendanceStatus

__all__ = [
    "record_checkin",
    "commit_decisions",
    "MIN_CHECKOUT_GAP_MINUTES",
    "Attendance",
    "AttendanceStatus",
    "kiosk_router",
    "attendance_manual_router",
    "kiosk_ws_router",
    "teacher_router",
]

_ROUTERS = {
    "kiosk_router": (".presentation.kiosk_routes", "router"),
    "attendance_manual_router": (".presentation.kiosk_routes", "manual_router"),
    "kiosk_ws_router": (".presentation.kiosk_ws", "router"),
    "teacher_router": (".presentation.teacher_routes", "router"),
}


def __getattr__(name: str):
    # Lazy: xem academic/public.py (kiosk_routes import academic/identity public).
    if name in _ROUTERS:
        import importlib

        mod_name, attr = _ROUTERS[name]
        mod = importlib.import_module(mod_name, __name__.rpartition(".")[0])
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

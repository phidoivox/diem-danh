from __future__ import annotations

from .application.build import (
    calculate_all_classes_exam_ban,
    calculate_class_exam_ban,
    generate_excel_exam_ban,
)
from .application.conduct import (
    CONDUCT_EXCEL_HEADERS,
    build_class_conduct_rows,
    generate_excel_conduct,
    parse_month_param,
    summarize_conduct,
)
from .application.history import build_student_history
from .infrastructure.repos import list_classes_ordered, list_enrolled_students

__all__ = [
    "CONDUCT_EXCEL_HEADERS",
    "build_class_conduct_rows",
    "generate_excel_conduct",
    "parse_month_param",
    "build_student_history",
    "list_classes_ordered",
    "list_enrolled_students",
    "summarize_conduct",
    "calculate_class_exam_ban",
    "calculate_all_classes_exam_ban",
    "generate_excel_exam_ban",
    "reporting_router",
    "student_portal_router",
    "settings_router",
    "files_router",
]

_ROUTERS = {
    "reporting_router": (".presentation.routes", "router"),
    "student_portal_router": (".presentation.portal_routes", "router"),
    "settings_router": (".presentation.settings_routes", "router"),
    "files_router": (".presentation.files_routes", "router"),
}


def __getattr__(name: str):
    # Lazy: xem academic/public.py (tránh circular import qua application.build).
    if name in _ROUTERS:
        import importlib

        mod_name, attr = _ROUTERS[name]
        mod = importlib.import_module(mod_name, __name__.rpartition(".")[0])
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

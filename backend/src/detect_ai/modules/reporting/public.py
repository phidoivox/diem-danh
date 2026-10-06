from __future__ import annotations

from .application.build import (
    calculate_all_classes_exam_ban,
    calculate_class_exam_ban,
    generate_excel_exam_ban,
)

__all__ = [
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

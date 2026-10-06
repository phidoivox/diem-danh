from __future__ import annotations

from .application.nightly import run_nightly_evaluation
from .domain.exam_ban import HALF_ABSENT_WEIGHT, converted_absent
from .domain.policy import decide_attendance
from .infrastructure.models import PointLedger  # noqa: F401

__all__ = [
    "HALF_ABSENT_WEIGHT",
    "PointLedger",
    "converted_absent",
    "decide_attendance",
    "run_nightly_evaluation",
    "evaluation_router",
]


def __getattr__(name: str):
    # Lazy: xem academic/public.py (tránh circular import qua application.nightly).
    if name == "evaluation_router":
        from .presentation.routes import router as evaluation_router

        return evaluation_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

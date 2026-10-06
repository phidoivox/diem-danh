from __future__ import annotations

"""Uniform hook + map decision legacy cho kiosk v2.

Logic ghi Attendance đã dời về `attendance.application.commit`
(recognition không import ngược attendance).
"""

from typing import Callable

import numpy as np

from .config import get_config
from .uniform_engine import UniformEngine, uniform_for_face

_uniform: UniformEngine | None = None


def uniform_hook_factory() -> Callable[..., object] | None:
    """Lazy singleton UniformEngine: 1 predict/frame (pipeline `uniform_predict`).

    Dual-mode để caller cũ (routes truyền positional vào `run_uniform`) không vỡ:
    1 arg (img) -> UniformDetections | None; 2 args (bbox, img) -> (status, reasons, score).
    ponytail: tach 2 factory khi routes chuyen sang `uniform_predict=` ro rang; ceiling = 2 callables.
    """
    global _uniform
    try:
        cfg = get_config()
    except Exception:
        return None
    if _uniform is None:
        try:
            _uniform = UniformEngine(imgsz=cfg.uniform_imgsz, conf=cfg.uniform_conf,
                                     provider=cfg.uniform_provider)
        except Exception:
            return None
    eng = _uniform

    def _predict(img_or_bbox: np.ndarray, img_bgr: np.ndarray | None = None):
        if img_bgr is None:
            try:
                return eng.predict(img_or_bbox)
            except Exception:
                return None
        try:
            det = eng.predict(img_bgr)
            st, _reasons, sc = uniform_for_face(img_or_bbox, det, iou_thr=cfg.uniform_iou_thr)
            return st, _reasons, sc
        except Exception:
            return "unknown", [], 0.0

    return _predict


def to_legacy(decision: str) -> str:
    """Map decision v2 -> chuỗi cũ cho frontend hiện tại."""
    return {
        "CONFIRMED": "CHECKED_IN",
        "PROVISIONAL": "VERIFYING",
        "CHALLENGE": "VERIFYING",
        "SPOOF": "SPOOF",
        "UNKNOWN": "UNKNOWN",
        "LOWQ": "LOWQ",
        "REJECTED": "VERIFYING",
    }.get(decision, decision)


__all__ = ["to_legacy", "uniform_hook_factory"]

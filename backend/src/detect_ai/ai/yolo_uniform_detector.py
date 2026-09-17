from __future__ import annotations
from pathlib import Path
import numpy as np
import supervision as sv
from loguru import logger
from ultralytics import YOLO
from ..core import config as C

class UniformDetector:
    def __init__(self, weights: str | None = None):
        p = Path(weights or C.YOLO_WEIGHTS)
        # ponytail: custom weights truoc, fallback pretrained khi chua train xong.
        self.model = YOLO(str(p) if p.exists() else C.YOLO_FALLBACK)
        model_classes = set(self.model.names.values())
        self.has_uniform_classes = bool({"valid_shirt", "invalid_shirt"} & model_classes)
        try:  # warmup: lan predict dau tien rat cham (init graph), lam truoc khi stream
            self.model.predict(np.zeros((384, 640, 3), np.uint8), conf=C.YOLO_CONF, imgsz=C.YOLO_IMGSZ, verbose=False)
        except Exception as e:
            logger.debug(f"yolo warmup skip: {e}")

    def predict(self, frame: np.ndarray) -> sv.Detections:
        r = self.model.predict(frame, conf=C.YOLO_CONF, imgsz=C.YOLO_IMGSZ, verbose=False)[0]
        return sv.Detections.from_ultralytics(r)

def uniform_status(names: list[str], has_uniform_model: bool = True) -> tuple[str, list[str]]:
    if not has_uniform_model:
        # Fallback khi chua train custom uniform weights (dang dung COCO model)
        return ("ok", [])
    s = set(names)
    bad: list[str] = []
    if "invalid_shirt" in s:
        bad.append("sai_ao")
    elif "valid_shirt" not in s:
        bad.append("thieu_ao_chuan")
    return ("ok" if not bad else "violation", bad)


def garments_of(det: sv.Detections, person_box: np.ndarray, names) -> list[str]:
    """Vector hoa: tim uniform box nam trong person box bang numpy, khong loop O(n^2)."""
    if len(det) == 0:
        return []
    x1, y1, x2, y2 = person_box
    b = det.xyxy
    inside = (b[:, 2] >= x1) & (b[:, 0] <= x2) & (b[:, 3] >= y1) & (b[:, 1] <= y2)
    return [names[int(c)] for c in det.class_id[inside]]

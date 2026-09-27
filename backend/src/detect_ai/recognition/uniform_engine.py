from __future__ import annotations

"""Uniform engine v2: ONNX-only bằng onnxruntime trực tiếp (bỏ torch lúc infer).

- .onnx -> onnxruntime InferenceSession + letterbox + NMS numpy (nhẹ,
  nhanh ~3x CPU theo docs Ultralytics, hỗ trợ OpenVINO/CUDA/DML).
- .pt chưa export -> lỗi rõ ràng hướng dẫn export (không fallback torch/supervision).
- Gán áo→người bằng IoU (face ⊂ person, thr 0.3).
- Chỉ gọi run-once lúc check-in (pipeline quyết định), không chạy mọi frame.
"""

from dataclasses import dataclass
from pathlib import Path
import threading

import numpy as np
from loguru import logger

DEFAULT_NAMES = ["person", "valid_shirt", "invalid_shirt"]


def resolve_weights(explicit: str | None = None) -> tuple[Path, str]:
    """Ưu tiên: explicit > custom uniform .pt > .onnx > fallback .pt."""
    try:
        from ..core import config as C

        if explicit:
            return Path(explicit), "explicit"
        custom = Path(C.YOLO_WEIGHTS)
        if custom.exists():
            return custom, "torch" if custom.suffix == ".pt" else "onnx"
        onnx = Path(C.YOLO_ONNX)
        if onnx.exists():
            return onnx, "onnx"
        return Path(C.YOLO_FALLBACK), "torch"
    except Exception:
        return Path(explicit or "yolo26n.pt"), "torch"


def _providers(explicit: str = "auto") -> list[str]:
    from ._providers import pick_providers

    chain, _ = pick_providers(explicit)
    return chain


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thr: float = 0.5) -> list[int]:
    """NMS numpy đơn giản. boxes (N,4) xyxy, scores (N,)."""
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    order = np.argsort(-scores)
    keep: list[int] = []
    while len(order):
        i = int(order[0])
        keep.append(i)
        if len(order) == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / np.maximum(1e-6, areas[i] + areas[order[1:]] - inter)
        order = order[1:][iou <= iou_thr]
    return keep


@dataclass
class UniformDetections:
    xyxy: np.ndarray  # (N,4)
    conf: np.ndarray  # (N,)
    class_id: np.ndarray  # (N,)
    names: list[str]

    def __len__(self) -> int:
        return int(self.xyxy.shape[0])


class UniformEngine:
    def __init__(self, weights: str | None = None, imgsz: int = 384,
                 conf: float = 0.35, provider: str = "auto", names: list[str] | None = None):
        self.path, self.kind = resolve_weights(weights)
        self.imgsz = max(256, int(imgsz or 384))
        self.conf = float(conf or 0.35)
        self.provider = provider or "auto"
        self.names = list(names or DEFAULT_NAMES)
        self._sess = None
        self._in_name = ""
        self._lock = threading.RLock()
        logger.info(f"[recognition v2] uniform weights={self.path.name} kind={self.kind} imgsz={self.imgsz}")

    def open(self):
        with self._lock:
            if self._sess is not None:
                return self
            if self.kind != "onnx" and not str(self.path).endswith(".onnx"):
                raise FileNotFoundError(
                    f"Uniform weights {self.path.name} chưa export ONNX. "
                    f"Chạy: cd backend && uv run python -m detect_ai.ai.export_yolo_onnx "
                    f"(supervision/torch fallback đã xóa cùng ai/ cũ)."
                )
            import onnxruntime as ort

            provs = _providers(self.provider)
            self._sess = ort.InferenceSession(str(self.path), providers=provs)
            self._in_name = self._sess.get_inputs()[0].name
            # Warmup
            try:
                self._sess.run(None, {self._in_name: np.zeros((1, 3, self.imgsz, self.imgsz), np.float32)})
            except Exception as e:  # noqa: BLE001
                logger.debug(f"[recognition v2] uniform onnx warmup skip: {e}")
            return self

    def _ensure(self):
        if self._sess is None:
            return self.open()
        return self

    def predict(self, img_bgr: np.ndarray) -> UniformDetections:
        with self._lock:
            self._ensure()
            return self._predict_onnx(img_bgr)

    def _predict_onnx(self, img_bgr: np.ndarray) -> UniformDetections:
        import cv2

        h0, w0 = img_bgr.shape[:2]
        s = self.imgsz / max(h0, w0)
        nw, nh = int(w0 * s), int(h0 * s)
        resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.imgsz, self.imgsz, 3), 114, dtype=np.uint8)
        dw, dh = (self.imgsz - nw) // 2, (self.imgsz - nh) // 2
        canvas[dh : dh + nh, dw : dw + nw] = resized
        rgb = canvas[:, :, ::-1].astype(np.float32) / 255.0
        inp = np.transpose(rgb, (2, 0, 1))[None, :, :, :].astype(np.float32)
        out = self._sess.run(None, {self._in_name: inp})[0]
        arr = np.asarray(out, dtype=np.float32)
        arr = arr[0]  # bỏ batch
        # Ultralytics ONNX: (4+nc, N) hoặc (N, 4+nc) — chuẩn hóa về (N, 4+nc)
        if arr.shape[0] < arr.shape[1] and arr.shape[0] <= 32:
            arr = arr.T
        if arr.shape[1] < 5:
            return UniformDetections(np.zeros((0, 4), np.float32), np.zeros((0,), np.float32),
                                     np.zeros((0,), np.int64), self.names)
        xywh, cls_scores = arr[:, :4], arr[:, 4:]
        nc = min(cls_scores.shape[1], len(self.names))
        cls_scores = cls_scores[:, :nc]
        best_cls = np.argmax(cls_scores, axis=1)
        best_conf = cls_scores[np.arange(len(best_cls)), best_cls]
        keep_mask = best_conf >= self.conf
        if not np.any(keep_mask):
            return UniformDetections(np.zeros((0, 4), np.float32), np.zeros((0,), np.float32),
                                     np.zeros((0,), np.int64), self.names)
        xywh, best_cls, best_conf = xywh[keep_mask], best_cls[keep_mask], best_conf[keep_mask]
        # xywh (letterbox) -> xyxy (ảnh gốc)
        cx, cy, bw, bh = xywh[:, 0], xywh[:, 1], xywh[:, 2], xywh[:, 3]
        x1 = (cx - bw / 2 - dw) / s
        y1 = (cy - bh / 2 - dh) / s
        x2 = (cx + bw / 2 - dw) / s
        y2 = (cy + bh / 2 - dh) / s
        boxes = np.stack([x1, y1, x2, y2], axis=1).astype(np.float32)
        boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, w0)
        boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, h0)
        keep = _nms(boxes, best_conf.astype(np.float32))
        return UniformDetections(boxes[keep], best_conf[keep].astype(np.float32),
                                 best_cls[keep].astype(np.int64), self.names)


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    aa = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    bb = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = aa + bb - inter
    return float(inter / union) if union > 0 else 0.0


def uniform_for_face(face_bbox: np.ndarray, det: UniformDetections,
                     iou_thr: float = 0.30) -> tuple[str, list[str], float]:
    """Gán đồng phục cho 1 mặt: tìm person chứa mặt (IoU cao nhất), rồi xem áo.

    Trả (status ok|violation, reasons, uniform_score).
    - Không có model uniform (COCO fallback): ("ok", [], 1.0)
    - Có model: violation khi có invalid_shirt trong person, hoặc thiếu valid_shirt.
    """
    names = det.names
    if not ({"valid_shirt", "invalid_shirt"} & set(names)):
        return "ok", [], 1.0
    if len(det) == 0:
        return "violation", ["thieu_ao_chuan"], 0.0
    fb = np.asarray(face_bbox, dtype=np.float32).reshape(4)
    persons = [(i, det.xyxy[i]) for i in range(len(det))
               if 0 <= int(det.class_id[i]) < len(names) and names[int(det.class_id[i])] == "person"]
    if not persons:
        # Không thấy person (ảnh chân dung sát mặt khi enroll): bỏ qua, không phạt oan
        return "ok", [], 1.0
    best_i, best_iou = -1, 0.0
    for i, pb in persons:
        # Mặt nằm trong person (containment) + IoU mặt-person làm tie-break
        inside = (pb[0] <= fb[0] + 5) and (pb[1] <= fb[1] + 5) and (pb[2] >= fb[2] - 5) and (pb[3] >= fb[3] - 5)
        s = _iou(fb, np.asarray(pb, dtype=np.float32)) + (1.0 if inside else 0.0)
        if s > best_iou:
            best_iou, best_i = s, i
    if best_i < 0:
        return "ok", [], 1.0
    pb = det.xyxy[best_i]
    shirts: list[str] = []
    for j in range(len(det)):
        cid = int(det.class_id[j])
        if cid < 0 or cid >= len(names):
            continue
        nm = names[cid]
        if nm not in ("valid_shirt", "invalid_shirt"):
            continue
        sb = det.xyxy[j]
        # Áo nằm trong person (giao nhau đủ lớn)
        ix1, iy1 = max(pb[0], sb[0]), max(pb[1], sb[1])
        ix2, iy2 = min(pb[2], sb[2]), min(pb[3], sb[3])
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        sa = max(1.0, (sb[2] - sb[0]) * (sb[3] - sb[1]))
        if inter / sa > 0.3:
            shirts.append(nm)
    if "invalid_shirt" in shirts:
        return "violation", ["sai_ao"], 0.2
    if "valid_shirt" not in shirts:
        return "violation", ["thieu_ao_chuan"], 0.4
    return "ok", [], 0.95

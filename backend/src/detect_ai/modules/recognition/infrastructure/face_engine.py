from __future__ import annotations

"""Face engine v2: wrapper InsightFace với lifecycle rõ ràng (DI, không singleton global).

Khác code cũ (ai/face_runtime.py):
- Không dùng global _app/_lock: mỗi FaceEngine 1 instance, 1 lock riêng.
  Test và multi-config không giẫm nhau.
- Input/output BGR như cũ (insightface tự xử RGB bên trong).
- quality() tách riêng, có thể mock.
"""

import threading
from dataclasses import dataclass

import cv2
import numpy as np
from loguru import logger


@dataclass
class Face:
    bbox: np.ndarray  # (4,) x1,y1,x2,y2 theo ảnh gốc
    det_score: float
    embedding: np.ndarray  # (512,) L2-normalized
    kps: np.ndarray | None = None  # (5,2) landmarks
    area: float = 0.0


def _l2norm(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v))
    return (v / n).astype(np.float32) if n > 0 else v


class FaceEngine:
    def __init__(self, pack: str = "auto", det_size: int = 256,
                 min_size: int = 45, max_faces: int = 3, max_width: int = 480):
        self.pack = (pack or "auto").strip().lower()
        self.det_size = max(160, int(det_size))
        self.min_size = max(20, int(min_size))
        self.max_faces = max(1, int(max_faces))
        self.max_width = max(320, int(max_width))
        self._lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self._app = None
        self._resolved_pack = ""

    def resolve_pack(self) -> str:
        if self.pack in ("buffalo_s", "buffalo_l"):
            return self.pack
        try:
            from ._providers import detect_runtime

            rt = detect_runtime()
            return "buffalo_l" if rt.has_gpu else "buffalo_s"
        except Exception:
            return "buffalo_s"

    def open(self):
        """Nạp model (lazy). Gọi 1 lần lúc startup/warmup."""
        with self._lock:
            if self._app is not None:
                return self._app
            from insightface.app import FaceAnalysis

            from ._providers import ctx_id_for, detect_runtime

            want = self.resolve_pack()
            try:
                rt = detect_runtime()
                ctx_id = ctx_id_for(rt.has_gpu)
            except Exception:
                ctx_id = -1
            app = FaceAnalysis(name=want)
            app.prepare(ctx_id=ctx_id, det_size=(self.det_size, self.det_size))
            self._app = app
            self._resolved_pack = want
            logger.info(f"[recognition v2] InsightFace pack={want} det={self.det_size} ctx={ctx_id}")
            try:
                app.get(np.zeros((480, 640, 3), np.uint8))
            except Exception as e:  # noqa: BLE001
                logger.debug(f"[recognition v2] warmup skip: {e}")
            return app

    def _ensure(self):
        if self._app is None:
            return self.open()
        return self._app

    def detect(self, img_bgr: np.ndarray) -> list[Face]:
        if img_bgr is None or img_bgr.size == 0:
            return []
        app = self._ensure()
        h0, w0 = img_bgr.shape[:2]
        if self.max_width > 0 and w0 > self.max_width:
            import cv2 as _cv

            s = self.max_width / float(w0)
            small = _cv.resize(img_bgr, (self.max_width, max(1, int(h0 * s))), interpolation=_cv.INTER_LINEAR)
            scale = s
        else:
            small, scale = img_bgr, 1.0
        with self._infer_lock:
            try:
                raw = app.get(small)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[recognition v2] insightface get() lỗi: {e}")
                return []
        out: list[Face] = []
        for f in raw:
            try:
                bbox = np.asarray(f.bbox, dtype=np.float32).reshape(4)
            except Exception:  # noqa: BLE001
                continue
            if scale != 1.0:
                bbox = (bbox / float(scale)).astype(np.float32)
                kps_raw = getattr(f, "kps", None)
                kps = (np.asarray(kps_raw, dtype=np.float32) / float(scale)) if kps_raw is not None else None
            else:
                kps = np.asarray(f.kps, dtype=np.float32) if getattr(f, "kps", None) is not None else None
            w, h = float(bbox[2] - bbox[0]), float(bbox[3] - bbox[1])
            if min(w, h) < self.min_size:
                continue
            raw_emb = getattr(f, "normed_embedding", None)
            if raw_emb is None:
                raw_emb = getattr(f, "embedding", None)
            if raw_emb is None:
                continue
            emb = _l2norm(np.asarray(raw_emb, dtype=np.float32))
            if emb.size == 0:
                continue
            out.append(Face(bbox=bbox, det_score=float(getattr(f, "det_score", 0.0) or 0.0),
                            embedding=emb, kps=kps, area=float(w * h)))
        out.sort(key=lambda r: r.area, reverse=True)
        return out[: self.max_faces]

    def describe(self) -> str:
        return f"pack={self.resolve_pack()} det={self.det_size} max_faces={self.max_faces}"


def quality(face: Face, img_bgr: np.ndarray) -> float:
    """Điểm chất lượng 0..1 (det + nét + sáng). Giữ công thức cũ đã tune."""
    q = float(face.det_score)
    x1, y1, x2, y2 = [int(v) for v in face.bbox]
    h, w = img_bgr.shape[:2]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    if x2 - x1 < 10 or y2 - y1 < 10:
        return 0.0
    crop = img_bgr[y1:y2, x1:x2]
    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        sharp = float(np.clip(blur / 120.0, 0.0, 1.0))
        bright = float(np.mean(gray) / 255.0)
        light = 1.0 - min(1.0, abs(bright - 0.5) * 2.0)
        q = 0.5 * q + 0.35 * sharp + 0.15 * light
    except Exception:  # noqa: BLE001
        pass
    return float(np.clip(q, 0.0, 1.0))


def embedding_to_json(emb: np.ndarray) -> str:
    import json

    return json.dumps([float(v) for v in np.asarray(emb, dtype=np.float32).reshape(-1)])


def json_to_array(raw: str) -> np.ndarray:
    import json

    arr = np.asarray(json.loads(raw), dtype=np.float32).reshape(-1)
    return _l2norm(arr)

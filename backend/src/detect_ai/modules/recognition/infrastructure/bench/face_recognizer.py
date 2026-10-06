from __future__ import annotations
import numpy as np
from loguru import logger

class FaceRecognizer:
    """InsightFace buffalo_s + liveness addon (observe). Spoof -> embed None."""

    def __init__(self):
        self.app = None

    def _load(self):
        if self.app is None:
            from insightface.app import FaceAnalysis
            from detect_ai.modules.recognition.infrastructure import config as C
            kw: dict = {"name": "buffalo_s", "providers": ["CPUExecutionProvider"]}
            if C.LIVENESS:  # liveness.onnx (~1.4MB) tu tai lan dau ve ~/.insightface/addons/
                kw.update(addons=["liveness"], liveness_mode="observe",
                          liveness_threshold=C.LIVENESS_THRESHOLD)
            self.app = FaceAnalysis(**kw)
            self.app.prepare(ctx_id=0, det_size=(C.FACE_DET_SIZE, C.FACE_DET_SIZE))
        return self.app

    def warmup(self):
        try:
            self.embed(np.zeros((160, 160, 3), np.uint8))
        except Exception as e:
            logger.debug(f"face warmup skip: {e}")

    def embed(self, bgr: np.ndarray, check_liveness: bool = True) -> np.ndarray | None:
        import cv2
        h, w = bgr.shape[:2]
        if max(h, w) > 320:  # crop nguoi thuong to, resize truoc khi insightface detect
            s = 320 / max(h, w)
            bgr = cv2.resize(bgr, (int(w * s), int(h * s)))
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        try:
            faces = self._load().get(rgb)
        except Exception as e:  # ponytail: addon loi (offline chua tai xong model) -> coi nhu khong thay mat
            logger.debug(f"face get skip: {e}")
            return None
        if not faces:
            return None
        f = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
        if check_liveness and not face_is_live(f):
            logger.debug("spoof face reject")
            return None
        if f.normed_embedding is None:
            return None
        v = np.asarray(f.normed_embedding, dtype=np.float32)
        return v / (np.linalg.norm(v) + 1e-9)


def face_is_live(f) -> bool:
    """True neu live hoac khong ket luan duoc (addon tat / input_rejected -> fail-open)."""
    lv = getattr(f, "liveness", None)
    if lv is None:
        return True
    return getattr(lv, "is_live", None) is not False


class FaceIndex:
    """faiss IndexFlatIP cho cosine similarity. Build 1 lan, search O(log n).

    Fallback numpy brute-force khi faiss absent (env test/dev nhẹ):
    cùng semantics (top-1 inner-product trên vector đã chuẩn hóa + ngưỡng).
    """

    def __init__(self, dim: int = 512):
        self.dim = dim
        try:
            import faiss

            self.index = faiss.IndexFlatIP(dim)
            self._faiss = True
        except ImportError:
            self._db = np.zeros((0, dim), np.float32)
            self._faiss = False

    def rebuild(self, embs: np.ndarray):
        if self._faiss:
            import faiss

            self.index = faiss.IndexFlatIP(self.dim)
            if len(embs):
                norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
                normed = (embs / norms).astype(np.float32)
                self.index.add(np.ascontiguousarray(normed))
            return
        arr = np.asarray(embs, dtype=np.float32).reshape(-1, self.dim)
        if len(arr):
            norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
            arr = (arr / norms).astype(np.float32)
        self._db = np.ascontiguousarray(arr)

    @property
    def ntotal(self) -> int:
        if self._faiss:
            return self.index.ntotal
        return len(self._db)

    def match(self, q: np.ndarray, thr: float) -> tuple[int, float]:
        if self._faiss:
            if self.index.ntotal == 0:
                return -1, 0.0
            q = np.asarray(q, dtype=np.float32).flatten()
            norm = np.linalg.norm(q)
            if norm > 1e-9:
                q = q / norm
            d, idx = self.index.search(q.reshape(1, -1).astype(np.float32), 1)
            sim = float(d[0][0])
            return (int(idx[0][0]), sim) if sim >= thr else (-1, 0.0)
        if len(self._db) == 0:
            return -1, 0.0
        q = np.asarray(q, dtype=np.float32).flatten()
        norm = np.linalg.norm(q)
        if norm > 1e-9:
            q = q / norm
        sims = self._db @ q
        j = int(np.argmax(sims))
        sim = float(sims[j])
        return (j, sim) if sim >= thr else (-1, 0.0)

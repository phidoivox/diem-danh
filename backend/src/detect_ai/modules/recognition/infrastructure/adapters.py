from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

from ..domain.ports import FacePort, LivenessPort, UniformPort
from . import liveness as live_mod
from .config import get_config
from .uniform_engine import UniformEngine

from .face_engine import FaceEngine


class FaceAdapter:
    """Adapts FaceEngine to FacePort."""

    def __init__(self, engine: FaceEngine | None = None) -> None:
        if engine is not None:
            self._engine = engine
        else:
            cfg = get_config()
            self._engine = FaceEngine(
                pack=cfg.face_pack,
                det_size=cfg.face_det_size,
                min_size=cfg.face_min_size,
                max_faces=cfg.face_max_faces,
                max_width=cfg.kiosk_max_width,
            )

    def detect(self, img_bgr: np.ndarray) -> list[Any]:
        return self._engine.detect(img_bgr)

    def identify(self, img_bgr: np.ndarray) -> list[dict[str, Any]]:
        faces = self._engine.detect(img_bgr)
        out: list[dict[str, Any]] = []
        for f in faces:
            out.append({
                "bbox": [float(v) for v in f.bbox],
                "det_score": float(f.det_score),
                "embedding": f.embedding.tolist() if hasattr(f.embedding, "tolist") else list(f.embedding),
                "area": float(getattr(f, "area", 0.0)),
            })
        return out


class LivenessAdapter:
    """Adapts liveness module to LivenessPort."""

    def check_live(
        self,
        img_bgr: np.ndarray,
        kps: np.ndarray | None = None,
        bbox: np.ndarray | None = None,
        live_thr: float = 0.8,
        challenge_low: float = 0.5,
    ) -> Any:
        return live_mod.check_live(
            img_bgr=img_bgr,
            kps=kps,
            bbox=bbox,
            live_thr=live_thr,
            challenge_low=challenge_low,
        )

    def check(self, img_bgr: np.ndarray, kps: Any = None) -> tuple[str, float]:
        verdict = live_mod.check_live(img_bgr=img_bgr, kps=kps)
        return verdict.verdict, float(verdict.score)


class UniformAdapter:
    """Adapts UniformEngine to UniformPort."""

    def __init__(self, engine: UniformEngine | None = None) -> None:
        self._engine = engine or UniformEngine()

    def predict(self, img_bgr: np.ndarray) -> Any:
        return self._engine.predict(img_bgr)

    def detect(self, img_bgr: np.ndarray) -> list[dict[str, Any]]:
        dets = self._engine.predict(img_bgr)
        out: list[dict[str, Any]] = []
        if dets is None or len(dets) == 0:
            return out
        for i in range(len(dets)):
            cid = int(dets.class_id[i])
            cname = dets.names[cid] if cid < len(dets.names) else str(cid)
            out.append({
                "box": [float(v) for v in dets.xyxy[i]],
                "confidence": float(dets.conf[i]),
                "class_id": cid,
                "label": cname,
            })
        return out


__all__ = ["FaceAdapter", "LivenessAdapter", "UniformAdapter"]

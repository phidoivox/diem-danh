from __future__ import annotations

"""Liveness v2: fail-closed + 2 cue + challenge hook.

Khác code cũ (ai/spoof_detector.py):
- Cũ thiếu model -> fail-open (live=1.0, cho qua). Mới: thiếu model -> REJECT.
- Cũ chỉ 1 cue InsightFace addons. Mới: cue1 InsightFace addons (căn mặt bằng
  kps, đúng cách chính chủ) + cue2 MiniFASNetV2 hook (optional, 2.7MB, 8ms CPU).
- Dải lưng chừng [challenge_low, live_thr) -> CHALLENGE (client MediaPipe làm
  blink/quay đầu), thay vì EMA phức tạp nằm rải rác ở pipeline cũ.
- Module này stateless (không giữ EMA/streak); smoothing theo track nằm ở pipeline.
"""

import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from loguru import logger


@dataclass
class LiveVerdict:
    verdict: str  # live | spoof | challenge | rejected | no_model
    score: float
    backend: str  # onnx-fusion | onnx-insightface | onnx-minifas | heuristic
    status: str  # ok | rejected | no-kps | no-model


_lock = threading.Lock()
_liveness = None
_liveness_path = ""
_minifas = None
_minifas_path = ""
_warned = False

OFFICIAL_THRESHOLD = 0.8


def resolve_insightface_model(explicit: str = "") -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    try:
        from detect_ai.core import config as C

        if getattr(C, "SPOOF_MODEL", ""):
            p = Path(C.SPOOF_MODEL)
            if p.exists():
                return p
    except Exception:
        pass
    default = Path.home() / ".insightface" / "addons" / "liveness.onnx"
    if default.exists() and default.stat().st_size > 100_000:
        return default
    return None


def resolve_minifas_model(explicit: str = "") -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.exists() and p.stat().st_size > 10_000 else None
    try:
        from .config import get_config

        cfg = get_config()
        if cfg.minifas_model:
            p = Path(cfg.minifas_model)
            if p.exists() and p.stat().st_size > 10_000:
                return p
    except Exception:
        pass
    # Vị trí quy ước: backend/data/weights/minifas_v2.onnx (tự tải, optional)
    try:
        from detect_ai.core import config as C

        base = Path(getattr(C, "DATA_DIR", "data"))
        for cand in (base / "weights" / "minifas_v2.onnx",
                     base / "weights" / "MiniFASNetV2.onnx"):
            if cand.exists() and cand.stat().st_size > 10_000:
                return cand
    except Exception:
        pass
    return None


def _get_insightface_liveness():
    global _liveness, _liveness_path
    path = resolve_insightface_model()
    with _lock:
        if path is None:
            return None
        if _liveness is None or _liveness_path != str(path):
            from insightface.addons.liveness import Liveness

            try:
                from ._providers import available_providers as _avail
            except ImportError:
                from detect_ai.recognition._providers import available_providers as _avail

            avail = set(_avail())
            order = ["CUDAExecutionProvider", "DmlExecutionProvider", "CoreMLExecutionProvider",
                     "OpenVINOExecutionProvider", "CPUExecutionProvider"]
            providers = [p for p in order if p in avail] or ["CPUExecutionProvider"]
            _liveness = Liveness(str(path), providers=providers)
            _liveness_path = str(path)
            logger.info(f"[recognition v2] liveness insightface={path.name} providers={providers}")
        return _liveness


def _insightface_score(img_bgr: np.ndarray, kps: np.ndarray | None) -> tuple[float, str]:
    """Trả (score, status). status: ok | rejected | no-kps | no-model."""
    adapter = _get_insightface_liveness()
    if adapter is None:
        return 0.0, "no-model"
    if kps is None:
        return 0.0, "no-kps"
    try:
        res = adapter.predict(img_bgr, np.asarray(kps, dtype=np.float32))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[recognition v2] liveness infer lỗi: {e}")
        return 0.0, "no-model"
    status = str(res.get("status") or "ok")
    if status != "ok":
        return 0.0, "rejected"
    return float(res.get("live_score") or 0.0), "ok"


def _minifas_score(img_bgr: np.ndarray, bbox: np.ndarray | None) -> tuple[float | None, str]:
    """MiniFASNetV2 hook (optional). Trả (score|None, backend).

    Chuẩn upstream: crop bbox scale 2.7x về 80x80 BGR/255, softmax 3-class,
    live = 1 - (p_print + p_replay). Chưa có file model -> (None, 'missing').

    LƯU Ý (verify 09/2026): MiniFAS công khai output hằng (09/2026) — chỉ dùng cue InsightFace.
    """
    global _minifas, _minifas_path
    path = resolve_minifas_model()
    if path is None:
        return None, "missing"
    try:
        import cv2
        import onnxruntime as ort

        with _lock:
            if _minifas is None or _minifas_path != str(path):
                _minifas = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
                _minifas_path = str(path)
        h, w = img_bgr.shape[:2]
        if bbox is not None and len(bbox) == 4:
            x1, y1, x2, y2 = [float(v) for v in bbox]
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
            s = 2.7 * max(bw, bh) / 2
            x1, y1, x2, y2 = cx - s, cy - s, cx + s, cy + s
            x1, y1, x2, y2 = max(0, int(x1)), max(0, int(y1)), min(w, int(x2)), min(h, int(y2))
            crop = img_bgr[y1:y2, x1:x2]
            if crop.size == 0:
                return None, "rejected"
        else:
            crop = img_bgr
        face = cv2.resize(crop, (80, 80), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        inp = np.transpose(face, (2, 0, 1))[None, :, :, :].astype(np.float32)  # NCHW BGR
        out = _minifas.run(None, {_minifas.get_inputs()[0].name: inp})[0]
        import math

        exps = [math.exp(float(v)) for v in np.asarray(out).reshape(-1)[:3]]
        tot = sum(exps) or 1.0
        probs = [e / tot for e in exps]
        live = 1.0 - (probs[1] + probs[2]) if len(probs) == 3 else float(probs[0])
        return float(np.clip(live, 0.0, 1.0)), "onnx-minifas"
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[recognition v2] minifas skip: {e}")
        return None, "error"


def check_live(img_bgr: np.ndarray, kps: np.ndarray | None = None,
               bbox: np.ndarray | None = None, live_thr: float = 0.80,
               challenge_low: float = 0.55) -> LiveVerdict:
    """Kết luận liveness 1 frame (fail-closed).

    - live: score >= live_thr (được vote)
    - challenge: score trong [challenge_low, live_thr) (cần blink/quay đầu)
    - spoof: score < challenge_low với status ok (ảnh giả rõ)
    - rejected: mặt sát viền/thiếu kps (chưa kết luận, giữ VERIFYING)
    - no_model: thiếu cả 2 model (chặn, không cho qua như code cũ)
    """
    global _warned
    s1, st1 = _insightface_score(img_bgr, kps)
    s2, _b2 = _minifas_score(img_bgr, bbox)
    if st1 == "no-model" and s2 is None:
        if not _warned:
            logger.warning("[recognition v2] thiếu model liveness -> REJECT (fail-closed). "
                           "Đặt liveness.onnx vào ~/.insightface/addons/ hoặc MiniFASNetV2 vào data/weights/.")
            _warned = True
        return LiveVerdict("no_model", 0.0, "none", "no-model")
    if st1 in ("rejected", "no-kps") and s2 is None:
        return LiveVerdict("rejected", 0.0, "onnx-insightface", st1)
    scores = []
    if st1 == "ok":
        scores.append(float(s1))
    if s2 is not None:
        scores.append(float(s2))
    if not scores:
        return LiveVerdict("rejected", 0.0, "onnx-insightface", st1)
    fused = float(sum(scores) / len(scores))
    backend = "onnx-fusion" if len(scores) == 2 else ("onnx-insightface" if st1 == "ok" else "onnx-minifas")
    if fused >= float(live_thr):
        return LiveVerdict("live", fused, backend, "ok")
    if fused >= float(challenge_low):
        return LiveVerdict("challenge", fused, backend, "ok")
    return LiveVerdict("spoof", fused, backend, "ok")

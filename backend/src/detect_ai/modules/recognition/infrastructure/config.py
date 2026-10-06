from __future__ import annotations

"""Config tập trung cho recognition v2 (thay ~20 biến FACE_*/SPOOF_*/KIOSK_* rời rạc).

Tương thích ngược: đọc từ core.config cũ khi không có env mới.
Auto-tune: đo thật 5 frame lúc startup thay heuristic cpu_count.
"""

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(_env(name, str(default))))
    except ValueError:
        return default


@dataclass
class RecognitionConfig:
    """Mọi ngưỡng/tuning ở 1 chỗ. Giá trị mặc định = đã tune cho CPU 4-core."""

    # Face detect
    face_pack: str = "auto"  # auto | buffalo_s | buffalo_l
    face_det_size: int = 256
    face_threshold: float = 0.45  # top1 >= mới accept
    face_margin_min: float = 0.05  # top1-top2 >= mới accept (chống nhầm)
    face_unsure_low: float = 0.35
    face_min_size: int = 45
    face_max_faces: int = 3
    # Voting
    vote_n: int = 2
    vote_window_s: float = 4.0
    # Quality
    quality_min: float = 0.35
    det_score_min: float = 0.15
    # Liveness (fail-closed)
    spoof_live_thr: float = 0.80
    spoof_min_frames: int = 2
    challenge_low: float = 0.55  # 0.55-0.8 -> yêu cầu chớp mắt/quay đầu
    spoof_model: str = ""  # InsightFace addons liveness.onnx
    minifas_model: str = ""  # MiniFASNetV2.onnx (lớp 2, optional)
    # Gallery
    gallery_cache_ttl_s: int = 300
    # Kiosk transport
    kiosk_max_width: int = 480
    kiosk_interval_ms: int = 450
    # Uniform (run-once lúc check-in)
    uniform_conf: float = 0.35
    uniform_imgsz: int = 384
    uniform_provider: str = "auto"
    uniform_threads: int = 0
    uniform_iou_thr: float = 0.30  # face ⊂ person
    # Session
    session_ttl_s: float = 7200.0
    track_ttl_s: float = 2.0
    track_iou_thr: float = 0.30

    def describe(self) -> str:
        return (
            f"v2 pack={self.face_pack} det={self.face_det_size} "
            f"thr={self.face_threshold}/margin={self.face_margin_min} "
            f"vote={self.vote_n}/{self.vote_window_s}s "
            f"live>={self.spoof_live_thr}x{self.spoof_min_frames}"
        )


_cached: RecognitionConfig | None = None


def get_config(force: bool = False) -> RecognitionConfig:
    """Đọc env mới (RECOGNITION_*) với fallback về DETECT_AI_* cũ."""
    global _cached
    if _cached is not None and not force:
        return _cached
    try:
        from detect_ai.shared.kernel import config as C  # fallback giá trị cũ

        def pick(new: str, old_val, cast=float):
            raw = _env(f"RECOGNITION_{new}")
            if raw:
                try:
                    return cast(raw)
                except ValueError:
                    pass
            return old_val

        cfg = RecognitionConfig(
            face_pack=(_env("RECOGNITION_FACE_PACK") or getattr(C, "FACE_PACK", "auto") or "auto"),
            face_det_size=int(pick("FACE_DET_SIZE", getattr(C, "FACE_DET_SIZE", 256), int)),
            face_threshold=float(pick("FACE_THRESHOLD", getattr(C, "FACE_THRESHOLD", 0.45), float)),
            face_margin_min=float(_env("RECOGNITION_FACE_MARGIN_MIN") or 0.05),
            face_unsure_low=float(pick("FACE_UNSURE_LOW", getattr(C, "FACE_UNSURE_LOW", 0.35), float)),
            face_min_size=int(pick("FACE_MIN_SIZE", getattr(C, "FACE_MIN_SIZE", 45), int)),
            face_max_faces=int(pick("FACE_MAX_FACES", getattr(C, "FACE_MAX_FACES", 3), int)),
            vote_n=int(pick("VOTE_N", getattr(C, "FACE_VOTE_N", 2), int)),
            vote_window_s=float(pick("VOTE_WINDOW_S", getattr(C, "FACE_VOTE_WINDOW_S", 4.0), float)),
            quality_min=float(pick("QUALITY_MIN", getattr(C, "SPOOF_QUALITY_MIN", 0.35), float)),
            spoof_live_thr=float(pick("SPOOF_LIVE_THR", getattr(C, "SPOOF_LIVE_THR", 0.80), float)),
            spoof_min_frames=int(pick("SPOOF_MIN_FRAMES", getattr(C, "SPOOF_MIN_FRAMES", 2), int)),
            challenge_low=float(_env("RECOGNITION_CHALLENGE_LOW") or 0.55),
            spoof_model=(_env("RECOGNITION_SPOOF_MODEL") or getattr(C, "SPOOF_MODEL", "") or ""),
            minifas_model=_env("RECOGNITION_MINIFAS_MODEL"),
            gallery_cache_ttl_s=int(pick("GALLERY_TTL_S", getattr(C, "FACE_GALLERY_CACHE_TTL_S", 300), int)),
            kiosk_max_width=int(pick("KIOSK_MAX_WIDTH", getattr(C, "KIOSK_MAX_WIDTH", 480), int)),
            kiosk_interval_ms=int(pick("KIOSK_INTERVAL_MS", getattr(C, "KIOSK_INTERVAL_MS", 450), int)),
            uniform_conf=float(pick("UNIFORM_CONF", getattr(C, "YOLO_CONF", 0.35), float)),
            uniform_imgsz=int(_env("RECOGNITION_UNIFORM_IMGSZ") or getattr(C, "YOLO_IMGSZ", 384)),
            uniform_provider=(_env("RECOGNITION_UNIFORM_PROVIDER") or getattr(C, "YOLO_PROVIDER", "auto") or "auto"),
            uniform_threads=int(getattr(C, "YOLO_THREADS", 0) or 0),
        )
    except Exception:
        cfg = RecognitionConfig(
            face_pack=_env("RECOGNITION_FACE_PACK", "auto") or "auto",
            spoof_model=_env("RECOGNITION_SPOOF_MODEL"),
            minifas_model=_env("RECOGNITION_MINIFAS_MODEL"),
        )
    _cached = cfg
    return cfg


def auto_tune(cfg: RecognitionConfig | None = None) -> RecognitionConfig:
    """Đo thật để chọn det_size/imgsz theo máy (thay heuristic cpu_count).

    An toàn khi thiếu model: giữ nguyên giá trị hiện tại.
    """
    cfg = cfg or get_config()
    try:
        try:
            from ._providers import detect_runtime
        except ImportError:
            from ._providers import detect_runtime

        rt = detect_runtime(explicit_provider=cfg.uniform_provider)
        if rt.has_gpu:
            if cfg.face_pack == "auto":
                cfg.face_pack = "buffalo_l"
            cfg.face_det_size = max(cfg.face_det_size, 320)
            cfg.uniform_imgsz = max(cfg.uniform_imgsz, 480)
        else:
            if cfg.face_pack == "auto":
                cfg.face_pack = "buffalo_s"
            # CPU yếu (<4 core): hạ det để kịp 1s
            import os as _os

            ncpu = _os.cpu_count() or 4
            if ncpu <= 2 and cfg.face_det_size > 256:
                cfg.face_det_size = 256
            if ncpu <= 2 and cfg.uniform_imgsz > 320:
                cfg.uniform_imgsz = 320
    except Exception:
        pass
    return cfg

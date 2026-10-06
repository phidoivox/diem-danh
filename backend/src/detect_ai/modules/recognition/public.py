from __future__ import annotations

from typing import Any

from .domain.ports import FacePort, LivenessPort, UniformPort
from .infrastructure.adapters import FaceAdapter, LivenessAdapter, UniformAdapter
from .infrastructure.config import RecognitionConfig, auto_tune, get_config
from .infrastructure.enroll import EnrollError, active_count, enroll_image, extract_best
from .infrastructure.gallery import Gallery, bump_db_version, bump_version, load_gallery, match
from .infrastructure.image import ImageDecodeError, decode_frame, decode_strict
from .infrastructure.image_service import decode_upload, save_attendance_snapshot, upload_avatar_image
from .infrastructure.models import FaceEmbedding, FaceEvent
from .infrastructure.pipeline import FaceDecision, KioskSession
from .infrastructure.service import to_legacy, uniform_hook_factory

from .infrastructure.face_engine import FaceEngine
from .infrastructure._providers import apply_cpu_threads, detect_runtime


def get_session(schedule_id: int, cfg: Any = None):
    from .infrastructure import pipeline as _p
    return _p.get_session(schedule_id, cfg)


def reset_session(schedule_id: int) -> None:
    from .infrastructure import pipeline as _p
    return _p.reset_session(schedule_id)


def discard_student(schedule_id: int, student_id: int) -> None:
    from .infrastructure import pipeline as _p
    return _p.discard_student(schedule_id, student_id)


def get_face_engine(engine: FaceEngine | None = None) -> FacePort:
    return FaceAdapter(engine=engine)


def get_liveness_engine() -> LivenessPort:
    return LivenessAdapter()


def get_uniform_engine(engine: Any = None) -> UniformPort:
    return UniformAdapter(engine=engine)


def get_engine(kind: str = "face", **kwargs: Any) -> FacePort | LivenessPort | UniformPort:
    """Factory creating engine port adapters."""
    k = (kind or "face").strip().lower()
    if k == "face":
        return get_face_engine(kwargs.get("engine"))
    if k == "liveness":
        return get_liveness_engine()
    if k == "uniform":
        return get_uniform_engine(kwargs.get("engine"))
    raise ValueError(f"Unknown engine kind: {kind}")


__all__ = [
    # Ports & Adapters
    "FacePort",
    "LivenessPort",
    "UniformPort",
    "FaceAdapter",
    "LivenessAdapter",
    "UniformAdapter",
    "get_engine",
    "get_face_engine",
    "get_liveness_engine",
    "get_uniform_engine",
    "FaceEngine",
    # Pipeline & Session
    "FaceDecision",
    "KioskSession",
    "get_session",
    "reset_session",
    "discard_student",
    # Service & Hook
    "to_legacy",
    "uniform_hook_factory",
    # Gallery & Enroll
    "Gallery",
    "load_gallery",
    "bump_version",
    "bump_db_version",
    "match",
    "enroll_image",
    "extract_best",
    "active_count",
    "EnrollError",
    # Config
    "RecognitionConfig",
    "get_config",
    "auto_tune",
    # Image
    "decode_frame",
    "decode_strict",
    "decode_upload",
    "upload_avatar_image",
    "ImageDecodeError",
    # Models
    "FaceEmbedding",
    "FaceEvent",
    "apply_cpu_threads",
    "detect_runtime",
    "warmup_face_engine",
]


def warmup_face_engine(engine: FacePort | None = None) -> str:
    """Mở model face lúc startup qua port (main gọi, không import FaceEngine concrete)."""
    # ponytail: FacePort chưa có open(); đi qua _engine nội bộ cùng module.
    # Promote open() lên FacePort + FaceAdapter khi chạm adapters (hiện cấm).
    cfg = auto_tune(get_config(force=True))
    eng = engine if engine is not None else get_face_engine()
    opener = getattr(getattr(eng, "_engine", None), "open", None)
    if opener is not None:
        opener()
    return cfg.describe()

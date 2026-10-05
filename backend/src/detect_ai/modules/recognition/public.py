from __future__ import annotations

from typing import Any

from .domain.ports import FacePort, LivenessPort, UniformPort
from .infrastructure.adapters import FaceAdapter, LivenessAdapter, UniformAdapter
from .infrastructure.config import RecognitionConfig, auto_tune, get_config
from .infrastructure.enroll import EnrollError, active_count, enroll_image
from .infrastructure.gallery import Gallery, bump_version, load_gallery, match
from .infrastructure.image import ImageDecodeError, decode_frame, decode_strict
from .infrastructure.models import FaceEmbedding, FaceEvent
from .infrastructure.pipeline import FaceDecision, KioskSession
from .infrastructure.service import to_legacy, uniform_hook_factory

try:
    from .infrastructure.face_engine import FaceEngine
except ImportError:
    from detect_ai.recognition.face_engine import FaceEngine


def get_session(schedule_id: int, cfg: Any = None):
    from .infrastructure import pipeline as _p
    return _p.get_session(schedule_id, cfg)


def reset_session(schedule_id: int) -> None:
    from .infrastructure import pipeline as _p
    return _p.reset_session(schedule_id)


async def commit_decisions(*args: Any, **kwargs: Any) -> Any:
    from .infrastructure import service as _s
    return await _s.commit_decisions(*args, **kwargs)


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
    # Service & Hook
    "commit_decisions",
    "to_legacy",
    "uniform_hook_factory",
    # Gallery & Enroll
    "Gallery",
    "load_gallery",
    "bump_version",
    "match",
    "enroll_image",
    "active_count",
    "EnrollError",
    # Config
    "RecognitionConfig",
    "get_config",
    "auto_tune",
    # Image
    "decode_frame",
    "decode_strict",
    "ImageDecodeError",
    # Models
    "FaceEmbedding",
    "FaceEvent",
]

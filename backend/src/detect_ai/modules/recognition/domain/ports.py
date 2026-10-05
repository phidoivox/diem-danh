from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import numpy as np


@runtime_checkable
class FacePort(Protocol):
    """Face detection & feature extraction port.

    Real engine methods: detect(img_bgr)
    Brief generic methods: identify(img_bgr)
    """

    def detect(self, img_bgr: np.ndarray) -> list[Any]: ...

    def identify(self, img_bgr: np.ndarray) -> list[dict[str, Any]]: ...


@runtime_checkable
class LivenessPort(Protocol):
    """Anti-spoofing liveness check port.

    Real engine methods: check_live(img_bgr, kps, bbox, live_thr, challenge_low)
    Brief generic methods: check(img_bgr, kps)
    """

    def check_live(
        self,
        img_bgr: np.ndarray,
        kps: np.ndarray | None = None,
        bbox: np.ndarray | None = None,
        live_thr: float = 0.8,
        challenge_low: float = 0.5,
    ) -> Any: ...

    def check(self, img_bgr: np.ndarray, kps: Any = None) -> tuple[str, float]: ...


@runtime_checkable
class UniformPort(Protocol):
    """Uniform / attire detection port.

    Real engine methods: predict(img_bgr)
    Brief generic methods: detect(img_bgr)
    """

    def predict(self, img_bgr: np.ndarray) -> Any: ...

    def detect(self, img_bgr: np.ndarray) -> list[dict[str, Any]]: ...


__all__ = ["FacePort", "LivenessPort", "UniformPort"]

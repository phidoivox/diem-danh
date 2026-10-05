from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np
import pytest

from detect_ai.modules.recognition.domain.ports import FacePort, LivenessPort, UniformPort
from detect_ai.modules.recognition.infrastructure.adapters import (
    FaceAdapter,
    LivenessAdapter,
    UniformAdapter,
)
from detect_ai.modules.recognition.public import (
    get_engine,
    get_face_engine,
    get_liveness_engine,
    get_uniform_engine,
)


@dataclass
class DummyFace:
    bbox: np.ndarray
    det_score: float
    embedding: np.ndarray
    area: float = 100.0


class FakeFaceEngine:
    def detect(self, img_bgr: np.ndarray) -> list[Any]:
        return [
            DummyFace(
                bbox=np.array([10.0, 20.0, 50.0, 60.0]),
                det_score=0.95,
                embedding=np.zeros((512,), dtype=np.float32),
                area=1600.0,
            )
        ]


class FakeUniformDetections:
    xyxy = np.array([[10.0, 20.0, 100.0, 200.0]], dtype=np.float32)
    conf = np.array([0.9], dtype=np.float32)
    class_id = np.array([1], dtype=np.int64)
    names = ["person", "valid_shirt", "invalid_shirt"]

    def __len__(self) -> int:
        return 1


class FakeUniformEngine:
    def predict(self, img_bgr: np.ndarray) -> Any:
        return FakeUniformDetections()


def test_face_adapter_and_port():
    fake = FakeFaceEngine()
    adapter = FaceAdapter(engine=fake)
    assert isinstance(adapter, FacePort)

    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    faces = adapter.detect(dummy_img)
    assert len(faces) == 1

    identified = adapter.identify(dummy_img)
    assert len(identified) == 1
    assert identified[0]["det_score"] == 0.95
    assert len(identified[0]["embedding"]) == 512
    assert identified[0]["bbox"] == [10.0, 20.0, 50.0, 60.0]


def test_liveness_adapter_and_port(monkeypatch):
    adapter = LivenessAdapter()
    assert isinstance(adapter, LivenessPort)

    from detect_ai.modules.recognition.infrastructure import liveness as live_mod

    @dataclass
    class FakeLiveVerdict:
        verdict: str = "live"
        score: float = 0.95
        backend: str = "test"
        status: str = "ok"

    monkeypatch.setattr(live_mod, "check_live", lambda *args, **kwargs: FakeLiveVerdict())

    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    v = adapter.check_live(dummy_img)
    assert v.verdict == "live"

    status, score = adapter.check(dummy_img)
    assert status == "live"
    assert score == 0.95


def test_uniform_adapter_and_port():
    fake = FakeUniformEngine()
    adapter = UniformAdapter(engine=fake)
    assert isinstance(adapter, UniformPort)

    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    dets = adapter.predict(dummy_img)
    assert len(dets) == 1

    res = adapter.detect(dummy_img)
    assert len(res) == 1
    assert res[0]["label"] == "valid_shirt"
    assert res[0]["confidence"] == pytest.approx(0.9, rel=1e-3)


def test_get_engine_factory():
    face_eng = get_engine("face", engine=FakeFaceEngine())
    assert isinstance(face_eng, FacePort)

    live_eng = get_engine("liveness")
    assert isinstance(live_eng, LivenessPort)

    uni_eng = get_engine("uniform", engine=FakeUniformEngine())
    assert isinstance(uni_eng, UniformPort)

    with pytest.raises(ValueError, match="Unknown engine kind"):
        get_engine("unknown")

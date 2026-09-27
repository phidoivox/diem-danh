"""Test recognition v2: gallery margin + IoU tracker + pipeline + service (không cần model thật)."""
from __future__ import annotations

from datetime import date, time

import numpy as np
import pytest
import pytest_asyncio

from detect_ai.recognition import gallery as gal_mod
from detect_ai.recognition.face_engine import Face
from detect_ai.recognition.gallery import Gallery, ProtoEntry, match
from detect_ai.recognition.liveness import LiveVerdict
from detect_ai.recognition.pipeline import KioskSession
from detect_ai.recognition.tracks import IoUTracker
from detect_ai.recognition.uniform_engine import UniformDetections, uniform_for_face


def _vec(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(512).astype(np.float32)
    return v / float(np.linalg.norm(v))


def _gallery() -> Gallery:
    v = _vec(7)
    v2 = _vec(99)
    entries = [ProtoEntry(1, "SV001", "An", [v, _vec(7001)]),
               ProtoEntry(2, "SV002", "Binh", [v2])]
    mat = np.stack([v, _vec(7001), v2])
    return Gallery(10, 0, entries, mat, np.asarray([1, 1, 2]), 0.0)


def test_match_margin_accept_unsure_unknown_empty():
    gal = _gallery()
    m = match(_vec(7), gal)
    assert m.decision == "accept" and m.student_id == 1 and m.margin >= 0.05
    # Vector gần ranh giới: vẫn unsure chứ không accept nhầm
    mid = (_vec(7) + _vec(99))
    mid = mid / float(np.linalg.norm(mid))
    m2 = match(mid, gal, threshold=0.99, unsure_low=0.2)
    assert m2.decision in ("unsure", "unknown")
    assert match(_vec(7), Gallery(10, 0, [], np.zeros((0, 512), np.float32),
                                 np.zeros((0,), np.int64), 0.0)).decision == "empty"


def test_match_same_student_protos_margin_zero_still_accepts():
    # 2 proto cùng SV giống nhau: runner khác SV xa -> margin lớn, accept
    gal = _gallery()
    m = match(_vec(7001), gal)
    assert m.student_id == 1 and m.decision == "accept"


def test_iou_tracker_stable_ids():
    tr = IoUTracker(iou_thr=0.3, ttl_s=2.0)
    b1 = [np.array([10, 10, 100, 120], np.float32)]
    a = tr.update(b1, now=0.0)
    b = tr.update([np.array([12, 12, 102, 122], np.float32)], now=0.4)
    assert a[0] == b[0]
    c = tr.update([np.array([400, 400, 500, 520], np.float32)], now=0.8)
    assert c[0] != a[0]


class _FakeFaceEngine:
    def __init__(self, face: Face):
        self._face = face

    def detect(self, img):
        return [self._face]


def _make_face(emb: np.ndarray) -> Face:
    return Face(bbox=np.array([100, 100, 200, 220], np.float32),
                det_score=0.9, embedding=emb, kps=np.zeros((5, 2), np.float32))


def test_pipeline_voting_confirmed_then_uniform_hook_once(monkeypatch):
    from detect_ai.recognition import pipeline as pipe_mod
    from detect_ai.recognition.config import RecognitionConfig

    gal = _gallery()
    face = _make_face(_vec(7))
    eng = _FakeFaceEngine(face)
    monkeypatch.setattr(pipe_mod.live_mod, "check_live",
                        lambda img, kps=None, bbox=None, **kw: LiveVerdict("live", 0.95, "onnx", "ok"))
    calls: list = []

    def hook(bbox, img):
        calls.append(1)
        return "ok", [], 0.95

    cfg = RecognitionConfig(vote_n=2, vote_window_s=4.0, spoof_min_frames=5)
    sess = KioskSession(schedule_id=101, face=eng, cfg=cfg)
    img = np.zeros((480, 640, 3), np.uint8)
    d1 = sess.process(img, gal, now=1000.0, run_uniform=hook)[0]
    assert d1.decision == "PROVISIONAL" and d1.votes == 1
    d2 = sess.process(img, gal, now=1000.8, run_uniform=hook)[0]
    assert d2.decision == "CONFIRMED" and d2.student_id == 1
    assert d2.uniform_status == "ok" and d2.uniform_score == 0.95
    # Frame sau: đã chốt -> vẫn CONFIRMED nhưng không cần vote lại
    d3 = sess.process(img, gal, now=1001.2, run_uniform=hook)[0]
    assert d3.decision == "CONFIRMED" and 1 in sess.done_students


def test_pipeline_spoof_needs_streak_and_fail_closed(monkeypatch):
    from detect_ai.recognition import pipeline as pipe_mod
    from detect_ai.recognition.config import RecognitionConfig

    gal = _gallery()
    eng = _FakeFaceEngine(_make_face(_vec(7)))
    monkeypatch.setattr(pipe_mod.live_mod, "check_live",
                        lambda img, kps=None, bbox=None, **kw: LiveVerdict("spoof", 0.1, "onnx", "ok"))
    cfg = RecognitionConfig(vote_n=2, spoof_min_frames=2)
    sess = KioskSession(schedule_id=102, face=eng, cfg=cfg)
    img = np.zeros((480, 640, 3), np.uint8)
    first = sess.process(img, gal, now=2000.0)[0]
    assert first.decision == "PROVISIONAL"  # frame xấu đầu chưa chốt
    second = sess.process(img, gal, now=2000.8)[0]
    assert second.decision == "SPOOF" and not sess.done_students


def test_pipeline_no_model_rejected(monkeypatch):
    from detect_ai.recognition import pipeline as pipe_mod
    from detect_ai.recognition.config import RecognitionConfig

    gal = _gallery()
    eng = _FakeFaceEngine(_make_face(_vec(7)))
    monkeypatch.setattr(pipe_mod.live_mod, "check_live",
                        lambda img, kps=None, bbox=None, **kw: LiveVerdict("no_model", 0.0, "none", "no-model"))
    sess = KioskSession(schedule_id=103, face=eng, cfg=RecognitionConfig())
    d = sess.process(np.zeros((480, 640, 3), np.uint8), gal, now=3000.0)[0]
    assert d.decision == "REJECTED"


def test_uniform_for_face_iou_association():
    det = UniformDetections(
        xyxy=np.array([[90, 80, 220, 400], [100, 150, 210, 350]], np.float32),
        conf=np.array([0.9, 0.9], np.float32),
        class_id=np.array([0, 1], np.int64),
        names=["person", "valid_shirt", "invalid_shirt"],
    )
    st, reasons, sc = uniform_for_face(np.array([100, 100, 200, 220], np.float32), det)
    assert (st, reasons) == ("ok", []) and sc > 0.9
    det2 = UniformDetections(
        xyxy=np.array([[90, 80, 220, 400], [100, 150, 210, 350]], np.float32),
        conf=np.array([0.9, 0.9], np.float32),
        class_id=np.array([0, 2], np.int64),
        names=["person", "valid_shirt", "invalid_shirt"],
    )
    st2, _, _ = uniform_for_face(np.array([100, 100, 200, 220], np.float32), det2)
    assert st2 == "violation"
    # Fallback COCO (không có class đồng phục): không phạt oan
    det3 = UniformDetections(np.zeros((0, 4), np.float32), np.zeros((0,), np.float32),
                             np.zeros((0,), np.int64), ["person"])
    assert uniform_for_face(np.array([100, 100, 200, 220], np.float32), det3)[0] == "ok"


def test_legacy_decision_map():
    from detect_ai.recognition.service import to_legacy

    assert to_legacy("CONFIRMED") == "CHECKED_IN"
    assert to_legacy("PROVISIONAL") == "VERIFYING"
    assert to_legacy("SPOOF") == "SPOOF"


def test_uniform_resolve_prefers_onnx_over_fallback(tmp_path, monkeypatch):
    from detect_ai.recognition.uniform_engine import resolve_weights

    onnx = tmp_path / "yolo26n.onnx"
    onnx.write_bytes(b"fake")
    # resolve_weights đọc core.config lười bên trong hàm
    import detect_ai.core.config as core_c

    monkeypatch.setattr(core_c, "YOLO_WEIGHTS", str(tmp_path / "nope.pt"), raising=False)
    monkeypatch.setattr(core_c, "YOLO_ONNX", str(onnx), raising=False)
    monkeypatch.setattr(core_c, "YOLO_FALLBACK", str(tmp_path / "fb.pt"), raising=False)
    path, kind = resolve_weights(None)
    assert kind == "onnx" and str(path) == str(onnx)


def test_image_decode_roundtrip():
    from detect_ai.recognition.image import decode_frame, encode_jpeg

    import cv2

    img = np.zeros((480, 640, 3), np.uint8)
    img[100:200, 100:200] = (0, 255, 0)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    back = decode_frame(buf.tobytes(), max_width=480)
    assert back.shape[1] == 480
    raw = encode_jpeg(back, quality=60)
    assert len(raw) > 1000


@pytest_asyncio.fixture
async def v2_seed(session_maker_fixture):
    from detect_ai.core.security import get_password_hash
    from detect_ai.models.academic import Class, ClassStudent, Schedule
    from detect_ai.models.face import FaceEmbedding
    from detect_ai.models.user import Role, StudentProfile, User
    from detect_ai.recognition.face_engine import embedding_to_json

    async with session_maker_fixture() as s:
        trole = Role(role_name="TEACHER")
        srole = Role(role_name="STUDENT")
        s.add_all([trole, srole])
        await s.commit()
        t = User(user_code="GVV2", full_name="G V V2", email="gvv2@x.vn",
                 password_hash=get_password_hash("Pass@123"), role_id=trole.id, is_active=True)
        st = User(user_code="SVV2", full_name="S V V2", email="svv2@x.vn",
                  password_hash=get_password_hash("Pass@123"), role_id=srole.id, is_active=True)
        s.add_all([t, st])
        await s.commit()
        await s.refresh(t)
        await s.refresh(st)
        s.add(StudentProfile(user_id=st.id, class_name="K1", major="CNTT", total_point=100))
        c = Class(class_code="VV201", course_name="V2 101", teacher_id=t.id,
                  semester="2026-1", total_sessions=15)
        s.add(c)
        await s.commit()
        await s.refresh(c)
        s.add(ClassStudent(class_id=c.id, student_id=st.id))
        sch = Schedule(class_id=c.id, room_name="P1", study_date=date.today(),
                       start_time=time(8, 0), end_time=time(10, 0), session_order=1)
        s.add(sch)
        s.add(FaceEmbedding(user_id=st.id, embedding=embedding_to_json(_vec(7)),
                            quality=0.9, source="avatar", is_active=True))
        await s.commit()
        yield {"teacher_id": t.id, "student_id": st.id, "class_id": c.id, "schedule_id": sch.id}


@pytest.mark.asyncio
async def test_v2_checkin_endpoint_idempotent(make_client, session_maker_fixture, v2_seed, monkeypatch):
    """POST /kiosk/checkin (engine v2) 2 lần cùng 1 mặt -> 1 row attendance."""
    import cv2
    from detect_ai.api import routes_kiosk
    from detect_ai.core.security import create_access_token
    from detect_ai.models.attendance_v2 import Attendance
    from detect_ai.recognition.pipeline import FaceDecision as V2Decision
    from sqlalchemy import func, select

    sid = v2_seed["student_id"]
    decisions = [V2Decision(1, [10, 10, 100, 120], sid, 0.9, 0.2, 0.95, "onnx", 0.9,
                            "CONFIRMED", 3, "ok", 0.95)]

    class FakeSession:
        def process(self, img, gallery, now=None, run_uniform=None):
            return decisions

    from detect_ai.recognition import pipeline as pipe_mod

    monkeypatch.setattr(pipe_mod, "get_session", lambda sched_id, cfg=None: FakeSession())

    ok, buf = cv2.imencode(".jpg", np.zeros((480, 640, 3), np.uint8))
    assert ok
    token = create_access_token({"sub": str(v2_seed["teacher_id"]), "role": "TEACHER"})
    headers = {"Authorization": f"Bearer {token}"}

    async with make_client() as client:
        for _ in range(2):
            r = await client.post(
                "/api/v1/kiosk/checkin",
                data={"schedule_id": str(v2_seed["schedule_id"])},
                files={"frame": ("frame.jpg", buf.tobytes(), "image/jpeg")},
                headers=headers,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["gallery_size"] == 1
            assert body["faces"][0]["decision"] == "CHECKED_IN"  # map từ CONFIRMED

    async with session_maker_fixture() as s:
        n = (await s.execute(select(func.count()).select_from(Attendance).where(
            Attendance.schedule_id == v2_seed["schedule_id"]))).scalar_one()
        assert n == 1


def test_orm_v2_columns_mapped():
    from detect_ai.models.attendance_v2 import Attendance
    from detect_ai.models.face import FaceEmbedding, FaceEvent
    assert "uniform_status" in Attendance.__table__.columns
    assert "uniform_score" in Attendance.__table__.columns
    assert "model_version" in FaceEmbedding.__table__.columns
    assert "det_score" in FaceEmbedding.__table__.columns
    assert "margin" in FaceEvent.__table__.columns
    assert "backend" in FaceEvent.__table__.columns

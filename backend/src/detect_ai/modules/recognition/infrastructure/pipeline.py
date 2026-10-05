from __future__ import annotations

"""Pipeline v2 thống nhất: face -> match (margin) -> liveness lazy -> vote -> uniform run-once.

4 trạng thái duy nhất (thay 7 trạng thái string cũ):
- CONFIRMED: đủ vote + live, chốt điểm danh
- PROVISIONAL: đang gom vote / chờ live (tên hiện ngay khi 1 frame tốt)
- CHALLENGE: điểm liveness lưng chừng, cần blink/quay đầu
- SPOOF: đủ N frame xấu liên tiếp
- UNKNOWN: không khớp gallery
- LOWQ: mặt mờ/nhỏ (bỏ qua, không vote)
- REJECTED: thiếu model liveness (fail-closed, không cho qua)

Uniform chỉ chạy 1 lần khi candidate sắp CONFIRMED (run_uniform callback),
dùng lại đúng frame đó — đúng yêu cầu "chấm 1 lần lúc check-in".
"""

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import liveness as live_mod
from .config import RecognitionConfig, get_config
try:
    from .face_engine import Face, FaceEngine, quality
except ImportError:
    from detect_ai.recognition.face_engine import Face, FaceEngine, quality
from .gallery import Gallery, match
from .tracks import IoUTracker
from .uniform_engine import uniform_for_face


@dataclass
class FaceDecision:
    track_id: int
    bbox: list[float]
    student_id: int | None
    score: float
    margin: float = 0.0
    liveness: float = 0.0
    liveness_backend: str = "-"
    quality: float = 0.0
    decision: str = "UNKNOWN"
    votes: int = 0
    uniform_status: str = "unknown"  # ok | violation | unknown
    uniform_score: float = 0.0
    uniform_det: object = None  # UniformDetections của đúng frame này (None = chưa infer/thiếu model)


@dataclass
class _Track:
    tid: int
    checked_student: int | None = None
    last_seen: float = 0.0
    spoof_streak: int = 0
    live_ema: float = 1.0
    live_score: float = 1.0
    live_backend: str = "-"
    uniform_done: dict[int, tuple[str, float]] = field(default_factory=dict)  # sid -> (status, score)


# run_uniform: (face_bbox, img_bgr) -> (status, reasons, score)
UniformHook = Callable[[np.ndarray, np.ndarray], tuple[str, list[str], float]]

# uniform_predict: (img_bgr) -> UniformDetections | None (1 infer/frame)
UniformPredict = Callable[[np.ndarray], object]


class KioskSession:
    """Trạng thái voting của 1 ca học. TTL 2h, thread-safe."""

    def __init__(self, schedule_id: int, face: FaceEngine | None = None,
                 cfg: RecognitionConfig | None = None, created_at: float | None = None):
        self.schedule_id = schedule_id
        self.cfg = cfg or get_config()
        self.face = face
        self.tracker = IoUTracker(iou_thr=self.cfg.track_iou_thr, ttl_s=self.cfg.track_ttl_s)
        self.tracks: dict[int, _Track] = {}
        self.done_students: set[int] = set()
        self.votes_by_sid: dict[int, deque] = {}
        self.created_at = created_at or time.monotonic()
        self.frames = 0
        self._lock = threading.Lock()

    def _get(self, tid: int) -> _Track:
        tr = self.tracks.get(tid)
        if tr is None:
            tr = _Track(tid=tid)
            self.tracks[tid] = tr
        return tr

    def process(self, img_bgr: np.ndarray, gallery: Gallery,
                now: float | None = None,
                run_uniform: UniformHook | None = None,
                uniform_predict: UniformPredict | None = None) -> list[FaceDecision]:
        cfg = self.cfg
        now = now if now is not None else time.monotonic()
        if len(gallery) == 0:
            return []
        engine = self.face or _shared_engine(cfg)
        faces: list[Face] = engine.detect(img_bgr)
        if not faces:
            return []
        id_map = self.tracker.update([f.bbox for f in faces], now)
        # Uniform: 1 infer/frame, chỉ khi có face accept tiềm năng.
        # ponytail: infer cả khi chưa biết accept (rẻ hơn per-face, đắt hơn lazy tuyệt đối); upgrade khi cần gate 2-pass.
        frame_det = None
        if uniform_predict is not None:
            try:
                frame_det = uniform_predict(img_bgr)
            except Exception:
                frame_det = None
        out: list[FaceDecision] = []
        with self._lock:
            self.frames += 1
            for i, f in enumerate(faces):
                x1, y1, x2, y2 = [float(v) for v in f.bbox]
                tid = int(id_map.get(i, 100000 + i))
                tr = self._get(tid)
                tr.last_seen = now
                # Quality gate
                if float(f.det_score or 0.0) < cfg.det_score_min:
                    out.append(FaceDecision(tid, [x1, y1, x2, y2], None, 0.0, 0.0, 0.0, "-", 0.0, "LOWQ"))
                    continue
                try:
                    q = float(quality(f, img_bgr))
                except Exception:
                    q = float(f.det_score or 0.0)
                if q < cfg.quality_min:
                    out.append(FaceDecision(tid, [x1, y1, x2, y2], None, 0.0, 0.0,
                                            tr.live_backend or "-", q, "LOWQ"))
                    continue
                # Match multi-prototype + margin
                m = match(f.embedding, gallery, threshold=cfg.face_threshold,
                          unsure_low=cfg.face_unsure_low, margin_min=cfg.face_margin_min)
                if m.decision != "accept":
                    dec = "UNKNOWN" if m.decision in ("unknown", "empty") else "PROVISIONAL"
                    out.append(FaceDecision(tid, [x1, y1, x2, y2], m.student_id, m.score, m.margin,
                                            tr.live_score, tr.live_backend or "-", q, dec))
                    continue
                sid = int(m.student_id) if m.student_id is not None else None
                # Liveness lazy: chỉ chạy cho candidate accept
                vd = live_mod.check_live(img_bgr, f.kps, np.asarray(f.bbox, dtype=np.float32),
                                         live_thr=cfg.spoof_live_thr, challenge_low=cfg.challenge_low)
                if vd.verdict == "no_model":
                    tr.live_score, tr.live_backend = 0.0, vd.backend
                    out.append(FaceDecision(tid, [x1, y1, x2, y2], sid, m.score, m.margin,
                                            0.0, vd.backend, q, "REJECTED"))
                    continue
                dq = self.votes_by_sid.setdefault(sid, deque()) if sid is not None else deque()
                if vd.verdict == "rejected":
                    out.append(FaceDecision(tid, [x1, y1, x2, y2], sid, m.score, m.margin,
                                            tr.live_score, vd.backend, q, "PROVISIONAL", len(dq)))
                    continue
                # Smoothing: EMA + streak (gọn hơn code cũ, nằm 1 chỗ)
                if len(dq) == 0 and tr.spoof_streak == 0 and tr.live_ema == 1.0:
                    tr.live_ema = float(vd.score)
                else:
                    tr.live_ema = 0.6 * float(vd.score) + 0.4 * float(tr.live_ema)
                if vd.verdict == "spoof":
                    tr.spoof_streak += 1
                elif vd.verdict == "live":
                    tr.spoof_streak = 0
                tr.live_score, tr.live_backend = float(vd.score), vd.backend
                if tr.spoof_streak >= max(1, cfg.spoof_min_frames):
                    dq.clear()
                    out.append(FaceDecision(tid, [x1, y1, x2, y2], sid, m.score, m.margin,
                                            float(vd.score), vd.backend, q, "SPOOF"))
                    continue
                if vd.verdict == "challenge":
                    out.append(FaceDecision(tid, [x1, y1, x2, y2], sid, m.score, m.margin,
                                            float(vd.score), vd.backend, q, "CHALLENGE", len(dq)))
                    continue
                if vd.verdict == "spoof" or tr.live_ema < cfg.spoof_live_thr:
                    out.append(FaceDecision(tid, [x1, y1, x2, y2], sid, m.score, m.margin,
                                            float(vd.score), vd.backend, q, "PROVISIONAL", len(dq)))
                    continue
                # Vote per-sid: sống qua đổi track ID (quay đầu/che)
                dq.append(now)
                while dq and now - dq[0] > cfg.vote_window_s:
                    dq.popleft()
                n = len(dq)
                # Uniform run-once khi sắp chốt (vote >= N-1) hoặc đã chốt
                u_status, u_score = "unknown", 0.0
                u_det = None
                if sid is not None and n >= max(1, cfg.vote_n - 1):
                    if frame_det is not None:
                        u_det = frame_det
                        try:
                            st, _reasons, sc = uniform_for_face(
                                np.asarray(f.bbox, dtype=np.float32), frame_det)
                            u_status, u_score = str(st), float(sc)
                        except Exception:
                            u_status, u_score = "unknown", 0.0
                    elif run_uniform is not None:
                        cached = tr.uniform_done.get(sid)
                        if cached is not None:
                            u_status, u_score = cached
                        else:
                            try:
                                st, _reasons, sc = run_uniform(np.asarray(f.bbox, dtype=np.float32), img_bgr)
                                u_status, u_score = str(st), float(sc)
                            except Exception:
                                u_status, u_score = "unknown", 0.0
                            tr.uniform_done[sid] = (u_status, u_score)
                if n >= cfg.vote_n and sid not in self.done_students:
                    self.done_students.add(sid)
                    tr.checked_student = sid
                    out.append(FaceDecision(tid, [x1, y1, x2, y2], sid, m.score, m.margin,
                                            float(vd.score), vd.backend, q, "CONFIRMED", n,
                                            u_status, u_score, u_det))
                else:
                    dec = "CONFIRMED" if sid in self.done_students else "PROVISIONAL"
                    out.append(FaceDecision(tid, [x1, y1, x2, y2], sid, m.score, m.margin,
                                            float(vd.score), vd.backend, q, dec, n, u_status, u_score,
                                            u_det))
            # GC tracks
            dead = [t for t, tr in self.tracks.items() if now - tr.last_seen > 30.0]
            for t in dead:
                del self.tracks[t]
        return out


_shared: FaceEngine | None = None
_shared_lock = threading.Lock()


def _shared_engine(cfg: RecognitionConfig) -> FaceEngine:
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = FaceEngine(pack=cfg.face_pack, det_size=cfg.face_det_size,
                                 min_size=cfg.face_min_size, max_faces=cfg.face_max_faces,
                                 max_width=cfg.kiosk_max_width)
        return _shared


_sessions: dict[int, KioskSession] = {}
_sessions_lock = threading.Lock()


def get_session(schedule_id: int, cfg: RecognitionConfig | None = None) -> KioskSession:
    cfg = cfg or get_config()
    with _sessions_lock:
        sess = _sessions.get(schedule_id)
        if sess is None or (time.monotonic() - sess.created_at > cfg.session_ttl_s):
            sess = KioskSession(schedule_id, cfg=cfg)
            _sessions[schedule_id] = sess
        return sess


def reset_session(schedule_id: int) -> None:
    with _sessions_lock:
        _sessions.pop(schedule_id, None)

from __future__ import annotations
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
import numpy as np
import supervision as sv
from detect_ai.modules.recognition.infrastructure import config as C
from .face_recognizer import FaceRecognizer
from .tracker import Tracker
from .yolo_uniform_detector import UniformDetector, garments_of, uniform_status

box_ann = sv.BoxAnnotator()
label_ann = sv.LabelAnnotator()

class Pipeline:
    def __init__(self, yolo: UniformDetector | None = None, face: FaceRecognizer | None = None):
        self.yolo = yolo if yolo is not None else UniformDetector()
        self.face = face if face is not None else FaceRecognizer()
        self.tracker = Tracker()
        self._seen: dict[int, float] = {}
        self._cnt: dict[int, int] = {}
        self._ids: dict[int, tuple[int, float]] = {}  # tid -> (db index, sim)
        self._lock = threading.Lock()
        # pool 1 worker: face chay nen khong chan frame, CPU khong don viec
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="face")
        self._pending: dict[int, Future] = {}
        self._gen = 0  # reset tang gen: callback cu khong ghi de _ids moi
        # warmup ca 2 model o init: request dau khong bi treo vai giay
        self.face.warmup()

    def reset(self):
        # Moi phien stream moi: tracker/ID cu giu lai gay loan box va nhan sai nguoi.
        # Pool cu shutdown (callback cu tu gen tang, khong ghi de _ids moi).
        self._gen += 1
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="face")
        self.tracker = Tracker()
        self._seen.clear()
        self._cnt.clear()
        self._ids.clear()
        self._pending.clear()

    def _cooldown(self, tid: int) -> bool:
        return time.time() - self._seen.get(tid, 0) < C.RELOG_COOLDOWN_S

    def _face_match(self, crop: np.ndarray, face_index) -> tuple[int, float] | None:
        v = self.face.embed(crop)
        if v is None:
            return None
        j, sim = face_index.match(v, C.FACE_SIM_THRESHOLD)
        return (j, sim) if j >= 0 else None

    def _face_done(self, fut: Future, tid: int, gen: int):
        try:
            hit = fut.result()
        except Exception:
            return
        if hit is not None and gen == self._gen:
            with self._lock:
                self._ids[tid] = hit

    def run(self, frame: np.ndarray, face_index, db_meta: list[dict], annotate: bool = True) -> tuple[np.ndarray, list[dict]]:
        raw_det = self.yolo.predict(frame)
        names = self.yolo.model.names
        if len(raw_det) > 0 and raw_det.class_id is not None:
            is_person = np.array([names.get(int(cid), "") == "person" for cid in raw_det.class_id])
            person_det = raw_det[is_person]
        else:
            person_det = raw_det

        det = self.tracker.update(person_det)
        out: list[dict] = []
        labels: list[str] = []
        tids = det.tracker_id if det.tracker_id is not None else []
        for xyxy, tid in zip(det.xyxy, tids):
            tid = int(tid)
            x1, y1, x2, y2 = map(int, xyxy)
            # garments_of: numpy vector hoa, thay loop long nhau O(n^2) cu
            status, bad = uniform_status(garments_of(raw_det, np.array([x1, y1, x2, y2]), names), self.yolo.has_uniform_classes)
            self._cnt[tid] = self._cnt.get(tid, 0) + 1
            code, disp, cls, sim = "unknown", "", "", 0.0
            with self._lock:
                hit = self._ids.get(tid)
            if hit is not None and 0 <= hit[0] < len(db_meta):
                m = db_meta[hit[0]]
                code, disp, cls, sim = m["code"], m.get("name", m["code"]), m.get("class_name", ""), hit[1]
            need_face = (
                len(db_meta)
                and code == "unknown"
                and not self._cooldown(tid)
                and self._cnt[tid] % C.RECOGNIZE_EVERY_N == 0
                and (x2 - x1) >= 60 and (y2 - y1) >= 60
            )
            if need_face:
                crop = frame[max(y1, 0):y2, max(x1, 0):x2].copy()
                if crop.size:
                    # don pending xong: chi submit khi pool ranh (giu nguong CPU cu)
                    self._pending = {t: f for t, f in self._pending.items() if not f.done()}
                    if tid not in self._pending and not self._pending:
                        fut = self._pool.submit(self._face_match, crop, face_index)
                        fut.add_done_callback(lambda f, t=tid, g=self._gen: self._face_done(f, t, g))
                        self._pending[tid] = fut
            labels.append(f"{disp or code} {status}")
            log = code != "unknown" and status == "ok" and not self._cooldown(tid)
            out.append({"tracker_id": tid, "bbox": [x1, y1, x2, y2], "student": code,
                        "name": disp, "class_name": cls,
                        "score": round(sim, 3), "uniform": status, "violations": bad, "log": log})
            if log:
                self._seen[tid] = time.time()
        if not annotate:
            return frame, out
        ann = label_ann.annotate(box_ann.annotate(frame, det), det, labels)
        return ann, out


_shared_yolo: UniformDetector | None = None
_shared_face: FaceRecognizer | None = None

def get_shared_models() -> tuple[UniformDetector, FaceRecognizer]:
    global _shared_yolo, _shared_face
    if _shared_yolo is None:
        _shared_yolo = UniformDetector()
    if _shared_face is None:
        _shared_face = FaceRecognizer()
    return _shared_yolo, _shared_face

def create_pipeline() -> Pipeline:
    yolo, face = get_shared_models()
    return Pipeline(yolo=yolo, face=face)

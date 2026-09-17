import numpy as np
import supervision as sv
from detect_ai.ai.yolo_uniform_detector import garments_of, uniform_status
from detect_ai.ai.face_recognizer import FaceIndex

# 1. uniform logic (chi kiem tra ao)
assert uniform_status(["person", "valid_shirt"]) == ("ok", [])
s, bad = uniform_status(["person", "invalid_shirt"])
assert s == "violation" and "sai_ao" in bad
s, bad = uniform_status(["person"])
assert s == "violation" and "thieu_ao_chuan" in bad
# Fallback model test: COCO model khong co lop dong phuc van cho phep pass
assert uniform_status(["person"], has_uniform_model=False) == ("ok", [])

# 2. garments_of vector hoa == loop cu (person box 0,0,100,100; uniform box trong/ngoai)
det = sv.Detections(
    xyxy=np.array([[0, 0, 100, 100], [10, 10, 50, 50], [200, 200, 300, 300]]),
    class_id=np.array([0, 1, 1]), confidence=np.array([0.9, 0.9, 0.9]))
names = {0: "person", 1: "valid_shirt"}
got = garments_of(det, np.array([0, 0, 100, 100]), names)
assert got == ["person", "valid_shirt"], got  # box ngoai (200,200) bi loai

# 3. faiss match == dot-product cu, tren DB ngau nhien
rng = np.random.default_rng(0)
db = rng.normal(size=(50, 512)).astype(np.float32)
db /= np.linalg.norm(db, axis=1, keepdims=True)
idx = FaceIndex()
idx.rebuild(db)
q = db[7]  # query trung 1 vector -> phai match index 7, sim ~1.0
j, sim = idx.match(q, 0.55)
assert j == 7 and sim > 0.99, (j, sim)
assert idx.match(rng.normal(size=512).astype(np.float32), 0.999) == (-1, 0.0)

print("pipeline self-check ok")

# 4. face_is_live: live/rejected/thieu addon -> pass, chi is_live=False -> chan
from types import SimpleNamespace
from detect_ai.ai.face_recognizer import face_is_live
assert face_is_live(SimpleNamespace(liveness=None))
assert face_is_live(SimpleNamespace(liveness=SimpleNamespace(is_live=True)))
assert face_is_live(SimpleNamespace(liveness=SimpleNamespace(is_live=None)))
assert not face_is_live(SimpleNamespace(liveness=SimpleNamespace(is_live=False)))

print("liveness self-check ok")

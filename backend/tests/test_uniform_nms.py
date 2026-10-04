import numpy as np
from detect_ai.recognition.uniform_engine import _nms


def test_nms_suppresses_overlapping_duplicate():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=np.float32)
    scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)
    keep = _nms(boxes, scores, iou_thr=0.5)
    assert 0 in keep and 2 in keep and 1 not in keep


def test_nms_empty_is_empty():
    assert _nms(np.zeros((0, 4), np.float32), np.zeros((0,), np.float32)) == []

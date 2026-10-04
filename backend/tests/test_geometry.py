import numpy as np
from detect_ai.recognition.geometry import iou


def test_iou_identical_boxes_is_one():
    a = np.array([0.0, 0.0, 10.0, 10.0], dtype=np.float32)
    assert iou(a, a) == 1.0


def test_iou_disjoint_boxes_is_zero():
    a = np.array([0.0, 0.0, 1.0, 1.0], dtype=np.float32)
    b = np.array([5.0, 5.0, 6.0, 6.0], dtype=np.float32)
    assert iou(a, b) == 0.0


def test_iou_zero_area_union_is_zero():
    a = np.array([2.0, 2.0, 2.0, 2.0], dtype=np.float32)
    b = np.array([2.0, 2.0, 2.0, 2.0], dtype=np.float32)
    assert iou(a, b) == 0.0

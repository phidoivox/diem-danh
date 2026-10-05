from __future__ import annotations

"""Tracker IoU nhẹ cho kiosk (thay ByteTrack khỏi đường face).

Lý do: kiosk cửa lớp max 3 mặt, ByteTrack+Kalman là overkill, lại trả
tracker_id=-1 phải fallback số ngẫu nhiên làm vỡ vote.
IoU greedy + TTL 2s là đủ ổn định, ~50 dòng, không thêm dependency.
"""

from dataclasses import dataclass

import numpy as np

from .geometry import iou as _iou


@dataclass
class TrackState:
    tid: int
    bbox: np.ndarray
    last_seen: float = 0.0
    missed: int = 0


class IoUTracker:
    """Gán ID ổn định bằng IoU greedy. Không Kalman, không ReID."""

    def __init__(self, iou_thr: float = 0.30, ttl_s: float = 2.0):
        self.iou_thr = float(iou_thr)
        self.ttl_s = float(ttl_s)
        self._tracks: dict[int, TrackState] = {}
        self._next_id = 1

    def update(self, boxes: list[np.ndarray], now: float) -> dict[int, int]:
        """Trả {index_face: track_id}."""
        # Dọn track quá hạn
        dead = [t for t, tr in self._tracks.items() if now - tr.last_seen > self.ttl_s]
        for t in dead:
            del self._tracks[t]
        if not boxes:
            return {}
        if not self._tracks:
            out = {}
            for i, b in enumerate(boxes):
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = TrackState(tid, np.asarray(b, dtype=np.float32), now)
                out[i] = tid
            return out
        tids = list(self._tracks.keys())
        nb, nt = len(boxes), len(tids)
        iou_mat = np.zeros((nb, nt), dtype=np.float32)
        for i, b in enumerate(boxes):
            ba = np.asarray(b, dtype=np.float32).reshape(4)
            for j, t in enumerate(tids):
                iou_mat[i, j] = _iou(ba, self._tracks[t].bbox)
        # Greedy theo IoU giảm dần
        pairs: list[tuple[float, int, int]] = []
        for i in range(nb):
            for j in range(nt):
                pairs.append((float(iou_mat[i, j]), i, j))
        pairs.sort(reverse=True)
        used_box, used_tr = set(), set()
        assign: dict[int, int] = {}
        for s, i, j in pairs:
            if s < self.iou_thr or i in used_box or j in used_tr:
                continue
            used_box.add(i)
            used_tr.add(j)
            tid = tids[j]
            assign[i] = tid
        for i, b in enumerate(boxes):
            ba = np.asarray(b, dtype=np.float32).reshape(4)
            if i in assign:
                self._tracks[assign[i]].bbox = ba
                self._tracks[assign[i]].last_seen = now
            else:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = TrackState(tid, ba, now)
                assign[i] = tid
        return assign

    def __len__(self) -> int:
        return len(self._tracks)

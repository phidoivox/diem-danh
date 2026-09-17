from __future__ import annotations
from supervision.tracker.byte_tracker.core import ByteTrack

class Tracker:
    def __init__(self):
        self.track = ByteTrack()

    def update(self, det: sv.Detections) -> sv.Detections:
        return self.track.update_with_detections(det)

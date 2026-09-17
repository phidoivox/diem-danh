from __future__ import annotations
import asyncio
import threading
import time
import cv2
import numpy as np
from ..ai.pipeline import create_pipeline
from ..core.config import FRAME_SIZE, INFER_INTERVAL_S, JPEG_QUALITY, RTSP_STREAM_FPS
from . import face_store
from .save_queue import put as save_put

# Doc RTSP bang ffmpeg pipe thay cv2.VideoCapture.read() blocking:
# mat goi khong treo ca loop, buffer -fflags nobuffer giam tre hinh.
FFMPEG = "ffmpeg"


class RtspWorker:
    def __init__(self):
        self.pipe = create_pipeline()
        self.proc = None
        self.url = ""
        self.live = False
        self.latest: np.ndarray | None = None  # frame tho moi nhat, stream hien thi truc tiep
        self.results: list[dict] = []  # ket qua AI frame gan nhat, client ve overlay rieng
        self.infer_ms = 0  # do tre AI vong gan nhat, client hien badge
        self.lock = threading.Lock()
        threading.Thread(target=self._capture_loop, daemon=True).start()
        threading.Thread(target=self._infer_loop, daemon=True).start()

    async def open(self, url: str):
        await self.close()
        import subprocess
        self.url = url
        # nobuffer + fps filter: frame ve deu, khong don cuc khi mang giat
        self.proc = subprocess.Popen(
            [FFMPEG, "-rtsp_transport", "tcp", "-fflags", "nobuffer", "-flags", "low_delay",
             "-i", url, "-vf", f"scale={FRAME_SIZE[0]}:{FRAME_SIZE[1]},fps=15",
             "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**7)
        self.live = True
        self.pipe.reset()
        await face_store.reload()

    async def close(self):
        self.live = False
        proc, self.proc = self.proc, None
        if proc:
            await asyncio.to_thread(proc.kill)
        with self.lock:
            self.latest = None
            self.results = []
            self.infer_ms = 0

    def _capture_loop(self):
        # Doc raw frame tu ffmpeg stdout, size co dinh -> khong decode JPEG ton CPU.
        n = FRAME_SIZE[0] * FRAME_SIZE[1] * 3
        while True:
            if self.live and self.proc and self.proc.stdout:
                raw = self.proc.stdout.read(n)
                if len(raw) == n:
                    f = np.frombuffer(raw, np.uint8).reshape(FRAME_SIZE[1], FRAME_SIZE[0], 3).copy()
                    with self.lock:
                        self.latest = f
                else:
                    time.sleep(0.05)
            else:
                time.sleep(0.1)

    def _infer_loop(self):
        # Inference nhịp rieng tren ban copy, khong bao gio chan capture/stream.
        while True:
            t0 = time.time()
            with self.lock:
                f = None if (not self.live or self.latest is None) else self.latest.copy()
            if f is not None:
                _, res = self.pipe.run(f, face_store.index, face_store.meta, annotate=False)
                for r in res:
                    if r["log"]:
                        save_put(r, f)
                with self.lock:
                    self.results = res
                    self.infer_ms = round((time.time() - t0) * 1000)
            time.sleep(max(0.0, INFER_INTERVAL_S - (time.time() - t0)))

    def mjpeg(self):
        # Stream frame tho toc do camera, khong doi AI -> video realtime, box ve sau vai tram ms.
        gap = 1.0 / RTSP_STREAM_FPS
        blank = np.zeros((*FRAME_SIZE[::-1], 3), np.uint8)
        while True:
            t0 = time.time()
            with self.lock:
                f = self.latest
                frame = blank if f is None else f
                _, b = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + b.tobytes() + b"\r\n"
            time.sleep(max(0.0, gap - (time.time() - t0)))

worker = RtspWorker()

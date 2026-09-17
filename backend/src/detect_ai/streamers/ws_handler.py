from __future__ import annotations
import asyncio
import base64
import time
import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from ..ai.pipeline import create_pipeline
from ..core.config import FRAME_SIZE
from . import face_store
from .save_queue import put as save_put

router = APIRouter()


def _decode(raw: bytes) -> np.ndarray | None:
    if raw.startswith(b"data:"):
        raw = base64.b64decode(raw.split(b",", 1)[1])
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    if img.shape[1] > FRAME_SIZE[0]:
        img = cv2.resize(img, FRAME_SIZE)
    return img


@router.websocket("/ws/attendance/webcam")
async def webcam(ws: WebSocket):
    await ws.accept()
    await face_store.reload()  # cache RAM 1 lan, khong query DB moi frame
    pipe = create_pipeline()  # tracker rieng per connection, AI model dung chung singleton
    latest: asyncio.Queue = asyncio.Queue(maxsize=1)  # chi giu frame moi nhat

    async def recv():
        # Nhan nhanh nhat co the, frame moi ghi de frame cu. Disconnect -> ca 2 task dung.
        while True:
            raw = await ws.receive_bytes()
            img = _decode(raw)  # decode nhe, khong can to_thread
            if img is None:
                continue
            if latest.full():
                try:
                    latest.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                latest.put_nowait(img)
            except asyncio.QueueFull:
                pass

    async def infer():
        # Lay frame moi nhat, chay xong moi lay tiep. Video hien thi local nen khong keo cham.
        while True:
            img = await latest.get()
            t0 = time.perf_counter()
            _, res = await asyncio.to_thread(pipe.run, img, face_store.index, face_store.meta, False)
            for r in res:
                if r["log"]:
                    save_put(r, img)  # queue chung, khong thread-moi-log
            await ws.send_json({"results": res, "infer_ms": round((time.perf_counter() - t0) * 1000)})

    recv_t = asyncio.create_task(recv())
    infer_t = asyncio.create_task(infer())
    _, pending = await asyncio.wait({recv_t, infer_t}, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    for t in (recv_t, infer_t):
        if not t.cancelled() and (e := t.exception()) is not None and not isinstance(e, WebSocketDisconnect):
            logger.debug(f"ws stop: {e}")

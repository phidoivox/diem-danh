from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from ..streamers.rtsp_worker import worker

router = APIRouter(prefix="/api/camera", tags=["camera"])

@router.post("/open")
async def open_cam(url: str):
    await worker.open(url)
    return {"ok": True}

@router.post("/close")
async def close_cam():
    await worker.close()
    return {"ok": True}

@router.get("/results")
async def results():
    with worker.lock:
        return {"results": worker.results, "infer_ms": worker.infer_ms, "live": worker.live}

@router.get("/stream")
async def stream():
    return StreamingResponse(worker.mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")

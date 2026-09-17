from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator
from .api.routes_attendance import router as att
from .api.routes_camera import router as cam
from .api.routes_students import router as stu
from .core.database import init_db
from .streamers.save_queue import saver_loop
from .streamers.ws_handler import router as ws

@asynccontextmanager
async def life(app: FastAPI):
    await init_db()
    task = asyncio.create_task(saver_loop())  # worker luu DB chay nen xuyen suot
    logger.info("detect-ai ready")
    yield
    task.cancel()

app = FastAPI(title="detect-ai", lifespan=life)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(stu)
app.include_router(att)
app.include_router(cam)
app.include_router(ws)
Instrumentator().instrument(app).expose(app)  # /metrics: thay badge infer_ms tay

@app.get("/api/health")
async def health():
    return {"ok": True}

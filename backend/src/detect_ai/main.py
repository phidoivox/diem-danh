from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator
from .api.routes_admin_academic import router as admin_academic
from .api.routes_admin_settings import router as admin_settings
from .api.routes_admin_users import router as admin_users
from .api.routes_attendance import router as att
from .api.routes_auth import router as auth
from .api.routes_camera import router as cam
from .api.routes_kiosk import router as kiosk
from .api.routes_leave_requests import router as leave_requests
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
app.include_router(auth, prefix="/api/v1/auth", tags=["auth"])
app.include_router(admin_users, prefix="/api/v1/admin/users", tags=["admin-users"])
app.include_router(admin_academic, prefix="/api/v1/admin/academic", tags=["admin-academic"])
app.include_router(admin_settings, prefix="/api/v1/admin/settings", tags=["admin-settings"])
app.include_router(kiosk, prefix="/api/v1/attendance")
app.include_router(leave_requests)
Instrumentator().instrument(app).expose(app)  # /metrics: thay badge infer_ms tay

@app.get("/api/health")
async def health():
    return {"ok": True}

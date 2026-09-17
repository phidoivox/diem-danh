from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .api.routes_admin_academic import router as admin_academic
from .api.routes_admin_settings import router as admin_settings
from .api.routes_admin_users import router as admin_users
from .api.routes_attendance import router as att
from .api.routes_auth import router as auth
from .api.routes_camera import router as cam
from .api.routes_evaluation import router as admin_evaluation
from .api.routes_kiosk import router as kiosk
from .api.routes_leave_requests import router as leave_requests
from .api.routes_students import router as stu
from .core.database import Session, init_db
from .services.evaluation_service import run_nightly_evaluation
from .streamers.save_queue import saver_loop
from .streamers.ws_handler import router as ws

@asynccontextmanager
async def life(app: FastAPI):
    await init_db()
    task = asyncio.create_task(saver_loop())  # worker luu DB chay nen xuyen suot

    scheduler = AsyncIOScheduler()

    async def nightly_cron_job():
        logger.info("Triggering nightly evaluation cron job (23:59)...")
        try:
            async with Session() as session:
                stats = await run_nightly_evaluation(session)
                logger.info(f"Nightly evaluation cron completed: {stats}")
        except Exception as e:
            logger.exception(f"Error in nightly evaluation cron job: {e}")

    scheduler.add_job(nightly_cron_job, "cron", hour=23, minute=59)
    scheduler.start()
    logger.info("detect-ai ready (Nightly evaluation cron scheduled for 23:59)")

    yield

    scheduler.shutdown(wait=False)
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
app.include_router(admin_evaluation, prefix="/api/v1/admin/evaluation", tags=["admin-evaluation"])
app.include_router(kiosk, prefix="/api/v1/attendance")
app.include_router(leave_requests)
Instrumentator().instrument(app).expose(app)  # /metrics: thay badge infer_ms tay

@app.get("/api/health")
async def health():
    return {"ok": True}

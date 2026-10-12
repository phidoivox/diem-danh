from __future__ import annotations
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.exc import IntegrityError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .modules.academic.public import academic_router as admin_academic
from .modules.reporting.public import reporting_router as admin_reports
from .modules.reporting.public import settings_router as admin_settings
from .modules.evaluation.public import evaluation_router as admin_evaluation
from .modules.attendance.public import attendance_manual_router as attendance_manual
from .modules.attendance.public import kiosk_router as kiosk
from .modules.attendance.public import kiosk_ws_router as kiosk_ws
from .modules.leave.public import leave_router as leave_requests
from .modules.reporting.public import student_portal_router as student_portal
from .modules.reporting.public import files_router as files
from .modules.attendance.public import teacher_router as teacher
from .modules.identity.public import admin_users_router as admin_users
from .modules.identity.public import auth_router as auth
from .modules.recognition.public import apply_cpu_threads, detect_runtime, get_engine, warmup_face_engine
from .shared.kernel.database import Session, init_db
from .shared.kernel.errors import AppError, app_error_handler, integrity_error_handler
from .shared.kernel.supabase import STORAGE_DIR
from .shared.kernel.timeutil import VN_TZ
from .modules.evaluation.public import run_nightly_evaluation


@asynccontextmanager
async def life(app: FastAPI):
    await init_db()
    # Kiosk fast-path: executor riêng cho Face/Spoof/IO để mỗi luồng không giẫm nhau.
    # Face/Spoof max 1 worker vì model ONNX/InsightFace không thread-safe khi infer
    # song song; frame bận thì drop ở tầng WS thay vì xếp hàng.
    import asyncio

    try:
        rt = detect_runtime()
        apply_cpu_threads(rt.threads)
        logger.info(f"AI runtime: provider={rt.provider} imgsz={rt.imgsz} threads={rt.threads}")
    except Exception as e:  # noqa: BLE001
        logger.debug(f"detect runtime skip: {e}")
    try:
        ncpu = os.cpu_count() or 4
        logger.info(f"ai runtime cpu={ncpu} (kiosk v2: infer sync trong WS, khong pool)")
    except Exception as e:  # noqa: BLE001
        logger.debug(f"runtime info skip: {e}")

    async def _warmup():
        try:
            desc = await asyncio.to_thread(warmup_face_engine, get_engine("face"))
            logger.info(f"recognition: {desc}")
            logger.info("kiosk warmup: insightface ready")
        except Exception as e:  # noqa: BLE001
            logger.debug(f"kiosk warmup skip: {e}")

    asyncio.get_running_loop().create_task(_warmup())

    scheduler = AsyncIOScheduler()

    async def nightly_cron_job():
        logger.info("Triggering nightly evaluation cron job (23:59)...")
        try:
            async with Session() as session:
                stats = await run_nightly_evaluation(session)
                logger.info(f"Nightly evaluation cron completed: {stats}")
        except Exception as e:
            logger.exception(f"Error in nightly evaluation cron job: {e}")

    async def reminder_cron_job():
        # Nhắc lịch học ngày mai lúc 20:00 VN.
        try:
            from detect_ai.shared.notifications import service as notif_service

            async with Session() as session:
                res = await notif_service.send_daily_reminders(session)
                logger.info(f"Daily reminder cron completed: {res}")
        except Exception as e:
            logger.exception(f"Error in daily reminder cron job: {e}")

    scheduler.add_job(nightly_cron_job, "cron", hour=23, minute=59, timezone=VN_TZ)
    scheduler.add_job(reminder_cron_job, "cron", hour=20, minute=0, timezone=VN_TZ)
    scheduler.start()
    logger.info("detect-ai ready (Nightly 23:59 + reminder 20:00, Asia/Ho_Chi_Minh)")

    yield

    scheduler.shutdown(wait=False)

app = FastAPI(title="detect-ai", lifespan=life)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(AppError, app_error_handler)


# Ảnh minh chứng / avatar khi chạy offline được ghi xuống đĩa và trả URL /static/storage/...
# Trước đây không mount nên các URL này luôn 404 -> ảnh minh chứng không hiển thị.
# CHỈ mount thư mục storage, tuyệt đối không mount DATA_DIR (sẽ lộ detect_ai.db).
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/storage", StaticFiles(directory=STORAGE_DIR), name="static-storage")
app.include_router(auth, prefix="/api/v1/auth", tags=["auth"])
app.include_router(admin_users, prefix="/api/v1/admin/users", tags=["admin-users"])
app.include_router(admin_academic, prefix="/api/v1/admin/academic", tags=["admin-academic"])
app.include_router(admin_settings, prefix="/api/v1/admin/settings", tags=["admin-settings"])
app.include_router(admin_evaluation, prefix="/api/v1/admin/evaluation", tags=["admin-evaluation"])
app.include_router(leave_requests)
app.include_router(student_portal)
app.include_router(teacher)
app.include_router(kiosk)
app.include_router(attendance_manual)
app.include_router(kiosk_ws)
app.include_router(admin_reports)
app.include_router(files)
Instrumentator().instrument(app).expose(app)  # /metrics: thay badge infer_ms tay

@app.get("/api/health")
async def health():
    return {"ok": True}

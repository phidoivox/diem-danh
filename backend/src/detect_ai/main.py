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
from .api.routes_admin_academic import router as admin_academic
from .api.routes_admin_reports import router as admin_reports
from .api.routes_admin_settings import router as admin_settings
from .api.routes_evaluation import router as admin_evaluation
from .api.routes_kiosk import router as kiosk
from .api.routes_kiosk_ws import router as kiosk_ws
from .api.routes_leave_requests import router as leave_requests
from .api.routes_student_portal import router as student_portal
from .api.routes_teacher import router as teacher
from .modules.identity.presentation.admin_routes import router as admin_users
from .modules.identity.presentation.routes import router as auth
from .shared.kernel.database import Session, init_db
from .shared.kernel.errors import integrity_error_handler
from .shared.kernel.supabase import STORAGE_DIR
from .services.evaluation_service import run_nightly_evaluation


@asynccontextmanager
async def life(app: FastAPI):
    await init_db()
    # Kiosk fast-path: executor riêng cho Face/Spoof/IO để mỗi luồng không giẫm nhau.
    # Face/Spoof max 1 worker vì model ONNX/InsightFace không thread-safe khi infer
    # song song; frame bận thì drop ở tầng WS thay vì xếp hàng.
    import asyncio
    from .recognition._providers import apply_cpu_threads, detect_runtime

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
            from .recognition.config import auto_tune, get_config
            from .recognition.face_engine import FaceEngine

            cfg = auto_tune(get_config(force=True))
            logger.info(f"recognition: {cfg.describe()}")
            await asyncio.to_thread(FaceEngine(pack=cfg.face_pack, det_size=cfg.face_det_size,
                                               min_size=cfg.face_min_size, max_faces=cfg.face_max_faces,
                                               max_width=cfg.kiosk_max_width).open)
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

    scheduler.add_job(nightly_cron_job, "cron", hour=23, minute=59)
    scheduler.start()
    logger.info("detect-ai ready (Nightly evaluation cron scheduled for 23:59)")

    yield

    scheduler.shutdown(wait=False)

app = FastAPI(title="detect-ai", lifespan=life)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


app.add_exception_handler(IntegrityError, integrity_error_handler)


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
app.include_router(kiosk_ws)
app.include_router(admin_reports)
Instrumentator().instrument(app).expose(app)  # /metrics: thay badge infer_ms tay

@app.get("/api/health")
async def health():
    return {"ok": True}

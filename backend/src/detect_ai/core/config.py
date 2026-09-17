from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
SNAPSHOT_DIR = DATA_DIR / "snapshots"
SNAPSHOT_DIR.mkdir(exist_ok=True)
PHOTO_DIR = DATA_DIR / "faces"
PHOTO_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'detect_ai.db'}"
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""
    supabase_db_url: str = ""
    kiosk_api_key: str = "kiosk-secret-key-2026"
    jwt_secret: str = "smart-classroom-super-secret-jwt-key-2026"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24

    @property
    def jwt_expire_minutes(self) -> int:
        return self.jwt_access_token_expire_minutes
    face_sim_threshold: float = 0.55
    yolo_conf: float = 0.35
    yolo_weights: str = str(DATA_DIR / "weights" / "uniform_yolo26.pt")
    yolo_fallback: str = "yolo26n.pt"
    require_id_card: bool = False
    recognize_every_n: int = 5  # face id nang: chay thua hon
    relog_cooldown_s: float = 30.0
    frame_w: int = 640
    frame_h: int = 480
    infer_interval_s: float = 0.12  # RTSP: toi da ~8fps inference
    jpeg_quality: int = 60
    yolo_imgsz: int = 384  # 448->384 giam ~30% CPU
    rtsp_stream_fps: int = 15
    face_det_size: int = 320
    liveness: bool = True
    liveness_threshold: float = 0.8

    model_config = {"env_prefix": "DETECT_AI_"}


S = Settings()

def _resolve_database_url(s: Settings) -> str:
    raw_url = s.supabase_db_url.strip() if s.supabase_db_url.strip() else s.database_url.strip()
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw_url

DATABASE_URL = _resolve_database_url(S)
SUPABASE_URL = S.supabase_url
SUPABASE_KEY = S.supabase_key or S.supabase_service_key
SUPABASE_SERVICE_KEY = S.supabase_service_key or S.supabase_key
SUPABASE_DB_URL = S.supabase_db_url
KIOSK_API_KEY = S.kiosk_api_key
JWT_SECRET = S.jwt_secret
JWT_ALGORITHM = S.jwt_algorithm
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = S.jwt_access_token_expire_minutes
FACE_SIM_THRESHOLD = S.face_sim_threshold
YOLO_CONF = S.yolo_conf
YOLO_WEIGHTS = S.yolo_weights
YOLO_FALLBACK = S.yolo_fallback
REQUIRE_ID_CARD = S.require_id_card
RECOGNIZE_EVERY_N = S.recognize_every_n
RELOG_COOLDOWN_S = S.relog_cooldown_s
FRAME_SIZE = (S.frame_w, S.frame_h)
INFER_INTERVAL_S = S.infer_interval_s
JPEG_QUALITY = S.jpeg_quality
YOLO_IMGSZ = S.yolo_imgsz
RTSP_STREAM_FPS = S.rtsp_stream_fps
FACE_DET_SIZE = S.face_det_size
LIVENESS = S.liveness
LIVENESS_THRESHOLD = S.liveness_threshold

UNIFORM_CLASSES = [
    "person",
    "valid_shirt",
    "invalid_shirt",
]

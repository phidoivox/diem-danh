from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parents[4]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
# SNAPSHOT_DIR / PHOTO_DIR đã bị xoá cùng lớp legacy (routes_students, routes_attendance,
# save_queue). Ảnh chân dung nay do admin upload qua /api/v1/admin/users (lưu local).


class Settings(BaseSettings):
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'detect_ai.db'}"
    supabase_db_url: str = ""
    # Rỗng mặc định: KHÔNG còn secret demo trong repo. Chạy thật bắt buộc đặt
    # DETECT_AI_JWT_SECRET (>= 32 ký tự), thiếu -> app từ chối khởi động (main.life).
    # Dev/test: đọc từ backend/.env; test không cần secret mạnh vì chỉ ký nội bộ.
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    # 8h = 1 ngày dạy. Đủ ngắn để thu hẹp cửa sổ token rò rỉ, đủ dài để GV
    # không bị văng giữa buổi. Có refresh flow thì hãy hạ tiếp.
    jwt_access_token_expire_minutes: int = 60 * 8
    # CORS allowlist (phân tách dấu phẩy). "*" bị cấm vì API dùng Bearer token:
    # bất kỳ origin nào cũng có thể gọi API bằng token đánh cắp.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # /metrics mặc định TẮT (lộ số liệu nội bộ). Bật khi có scraper nội bộ.
    expose_metrics: bool = False
    # Rate-limit login: mỗi tài khoản 10 lần SAI/phút + mỗi IP 60 lần SAI/phút.
    # Chỉ lần sai mới đếm (login đúng free) nên cả trường chung 1 IP giờ cao
    # điểm không tự khóa nhau; chi tiết ở api/rate_limit.py.
    login_rate_limit_per_account_per_minute: int = 10
    login_rate_limit_per_ip_per_minute: int = 60
    # WS kiosk: tối đa kết nối/phút/IP (chống giữ socket đốt CPU).
    ws_connects_per_ip_per_minute: int = 20
    # Tin X-Forwarded-For khi đọc IP rate-limit. CHỈ bật khi chạy sau reverse
    # proxy mình kiểm soát (proxy strip header từ client). Bật sau proxy lạ =
    # attacker tự đặt IP bất kỳ -> bypass rate-limit.
    trust_proxy: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in (self.cors_origins or "").split(",") if o.strip()]
        if "*" in origins:
            raise ValueError(
                "DETECT_AI_CORS_ORIGINS chứa '*': API dùng Bearer token, "
                "wildcard cho phép mọi origin gọi API bằng token đánh cắp. "
                "Liệt kê origin rõ ràng."
            )
        return origins

    @property
    def jwt_expire_minutes(self) -> int:
        return self.jwt_access_token_expire_minutes
    yolo_conf: float = 0.35
    yolo_weights: str = str(DATA_DIR / "weights" / "uniform_yolo26.pt")
    yolo_fallback: str = "yolo26n.pt"
    yolo_onnx: str = str(DATA_DIR / "weights" / "yolo26n.onnx")
    yolo_provider: str = "auto"
    yolo_threads: int = 0
    frame_w: int = 640
    frame_h: int = 480
    infer_interval_s: float = 0.12  # RTSP: toi da ~8fps inference
    jpeg_quality: int = 60
    yolo_imgsz: int = 384  # 384 giu do chinh xac va toc do cao
    rtsp_stream_fps: int = 15

    # ===== Face Kiosk (InsightFace + Liveness) =====
    # pack: auto = buffalo_l khi có GPU, buffalo_s khi CPU-only.
    # Defaults đã tune cho mục tiêu 1s thấy mặt / 2s chốt người trên CPU 4-core:
    # vote 2 lần/4s thay vì 3/2s (tránh miss do latency), det 256 + max 3 mặt.
    face_pack: str = "auto"
    face_det_size: int = 256  # 256 nhanh (~1.5x so với 320), 320 chỉ khi GPU
    face_threshold: float = 0.45  # cosine >= ngưỡng mới accept
    face_unsure_low: float = 0.35  # 0.35-0.45 = unsure, không điểm danh
    face_vote_n: int = 2  # số lần match cùng 1 SV trong cửa sổ vote mới chốt
    face_vote_window_s: float = 4.0
    face_min_size: int = 45  # mặt nhỏ hơn (px, theo cạnh ngắn bbox) thì bỏ
    face_max_faces: int = 3  # kiosk cửa lớp: chỉ 3 mặt to nhất, tránh O(N) lag
    spoof_threshold: float = 0.8  # ngưỡng chính chủ InsightFace; < ngưỡng = spoof
    spoof_live_thr: float = 0.8  # >= ngưỡng này mới được vote (ảnh giả chập chờn khó lọt)
    spoof_min_frames: int = 2  # cần N lần nghi liên tiếp mới chốt SPOOF (chống flicker)
    spoof_quality_min: float = 0.35  # quality_of() dưới ngưỡng -> UNSURE, không chạy liveness
    spoof_model: str = ""  # rỗng = tự tìm ~/.insightface/addons/liveness.onnx
    face_gallery_cache_ttl_s: int = 300  # TTL cache gallery theo lớp
    # Kiosk fast-path: ảnh gửi lên tối đa 480px, server resize trước infer.
    kiosk_max_width: int = 480
    kiosk_interval_ms: int = 450  # client gửi mỗi ~450ms, 1 in-flight

    # ===== Tầng CSDL =====
    # 0 = tự chọn theo chế độ (SQLite / Postgres thường / Supabase)
    db_pool_size: int = 0
    db_max_overflow: int = 0
    # False = KHÔNG tự create_all khi khởi động; schema do các file trong backend/sql/ sở hữu.
    # Khuyến nghị đặt false khi chạy trên Supabase để tránh hai nguồn sự thật về schema.
    auto_create_tables: bool = True

    # env_file: KHÔNG có dòng này thì pydantic-settings bỏ qua hoàn toàn file backend/.env
    # và chỉ đọc biến môi trường thật -> làm đúng theo hướng dẫn "cp .env.example .env"
    # cũng không có tác dụng gì, backend vẫn chạy SQLite.
    # Dùng đường dẫn tuyệt đối để không phụ thuộc CWD (uvicorn có thể chạy từ gốc repo).
    # extra="ignore": .env cũ còn sót biến FaceID/Kiosk đã bỏ (DETECT_AI_LIVENESS...)
    # không được làm sập app khi nâng cấp.
    model_config = {
        "env_prefix": "DETECT_AI_",
        "env_file": str(BASE_DIR / ".env"),
        "extra": "ignore",
    }


S = Settings()

def _resolve_database_url(s: Settings) -> str:
    raw_url = s.supabase_db_url.strip() if s.supabase_db_url.strip() else s.database_url.strip()
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw_url

DATABASE_URL = _resolve_database_url(S)
SUPABASE_DB_URL = S.supabase_db_url
JWT_SECRET = S.jwt_secret
JWT_ALGORITHM = S.jwt_algorithm
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = S.jwt_access_token_expire_minutes
YOLO_CONF = S.yolo_conf
YOLO_WEIGHTS = S.yolo_weights
YOLO_FALLBACK = S.yolo_fallback
YOLO_ONNX = S.yolo_onnx
YOLO_PROVIDER = S.yolo_provider
YOLO_THREADS = max(0, int(S.yolo_threads))
FRAME_SIZE = (S.frame_w, S.frame_h)
INFER_INTERVAL_S = S.infer_interval_s
JPEG_QUALITY = S.jpeg_quality
YOLO_IMGSZ = S.yolo_imgsz
RTSP_STREAM_FPS = S.rtsp_stream_fps

# Face Kiosk (InsightFace + Liveness passive)
FACE_PACK = (S.face_pack or "auto").strip().lower()
FACE_DET_SIZE = max(160, int(S.face_det_size))
FACE_THRESHOLD = float(S.face_threshold)
FACE_UNSURE_LOW = float(S.face_unsure_low)
FACE_VOTE_N = max(1, int(S.face_vote_n))
FACE_VOTE_WINDOW_S = max(0.5, float(S.face_vote_window_s))
FACE_MIN_SIZE = max(20, int(S.face_min_size))
FACE_MAX_FACES = max(1, int(S.face_max_faces))
SPOOF_THRESHOLD = float(S.spoof_threshold)
SPOOF_LIVE_THR = float(S.spoof_live_thr or S.spoof_threshold)
SPOOF_MIN_FRAMES = max(1, int(S.spoof_min_frames))
SPOOF_QUALITY_MIN = float(S.spoof_quality_min)
SPOOF_MODEL = (S.spoof_model or "").strip()
FACE_GALLERY_CACHE_TTL_S = max(30, int(S.face_gallery_cache_ttl_s))
KIOSK_MAX_WIDTH = max(320, int(S.kiosk_max_width))
KIOSK_INTERVAL_MS = max(120, int(S.kiosk_interval_ms))

UNIFORM_CLASSES = [
    "person",
    "valid_shirt",
    "invalid_shirt",
]

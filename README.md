# Hệ thống Quản lý Lớp học Thông minh (Smart Classroom Management System)

Hệ thống điểm danh và quản lý chuyên cần với 3 phân hệ Portal
(**Sinh viên – Giảng viên – Quản trị viên**), luồng **đơn xin nghỉ phép trực tuyến kèm minh chứng**, động cơ
**tính điểm chuyên cần tự động 23h59 (Idempotent Cron + Point Ledger)** và **xuất báo cáo cấm thi chuẩn quy chế**
(file Excel) trên nền tảng Supabase.

---

## 1. Tính năng chính

### 1.1 Điểm danh (giảng viên ghi nhận)
- Giảng viên điểm danh thủ công từng buổi (Manual Override kèm ghi chú) trên trang live của lớp.
- **Kiosk khuôn mặt** (`/teacher/classes/[id]/kiosk`): camera cửa lớp → InsightFace + liveness → tự check-in sau voting 2 lần/4s (xem `backend/sql/04_face_tables.sql`).
- Tự động phân định **Check-in / Check-out** theo ca học (Cron suy luận PRESENT / LATE / HALF_ABSENT từ giờ check-in/out).
- Ghi nhận **đồng phục hợp lệ / vi phạm** theo từng lượt.

### 1.2 Phân hệ Sinh viên
- Thời khóa biểu cá nhân, lịch sử điểm danh theo từng buổi (Có mặt / Muộn / Nghỉ có phép / Vắng).
- Sổ cái điểm rèn luyện (`point_ledger`) kèm tổng điểm hiện tại và diễn giải từng biến động.
- Nộp đơn xin nghỉ phép trực tuyến kèm minh chứng (JPEG/PNG/PDF ≤ 5MB) và theo dõi trạng thái duyệt.

### 1.3 Phân hệ Giảng viên
- Danh sách lớp học phần phụ trách; **Sĩ số thời gian thực** (đã check-in, chưa tới, vi phạm đồng phục).
- **Sửa điểm danh thủ công** (Manual Override) kèm ghi chú — Cron 23h59 luôn tôn trọng cờ này.
- Duyệt / từ chối đơn nghỉ phép, xem minh chứng dạng modal phóng to.
- **Báo cáo cấm thi từng môn** + tải file Excel `.xlsx`.

### 1.4 Phân hệ Quản trị viên
- CRUD người dùng (kèm upload ảnh chân dung), xoá mềm (`deleted_at`).
- Quản lý lớp học phần, ghi danh sinh viên, xếp thời khoá biểu **chống trùng phòng học**.
- Cấu hình tham số chấm điểm / ngưỡng trễ / bắt buộc check-out.
- **Báo cáo cấm thi toàn trường** + nút **"Chạy tính điểm hôm nay"** (chạy bù Cron 23h59).

---

## 2. Kiến trúc & Công nghệ

| Tầng | Công nghệ |
| --- | --- |
| **Database** | Supabase PostgreSQL (11 bảng 3NF, trạng thái `VARCHAR + CHECK`, soft delete) + Supabase Storage (`leave-proofs`, `avatars`) |
| **Backend** | FastAPI, Python 3.12, SQLAlchemy 2.0 Async (`asyncpg` / `aiosqlite`), Pydantic v2, python-jose (JWT), Passlib (Bcrypt), APScheduler, OpenPyXL, storage3 (Supabase Storage) |
| **AI Engine** | YOLO26 ONNX (đồng phục, run-once lúc check-in) · **InsightFace buffalo_s/l + Liveness fail-closed (kiosk điểm danh khuôn mặt, `POST /api/v1/kiosk/checkin`)** · Gallery multi-prototype + margin, tracker IoU (xem `backend/src/detect_ai/recognition/`) |
| **Frontend** | Next.js 16 (App Router), React 19, Tailwind CSS v4, Lucide Icons — phong cách **SaaS quản trị (Linear/Stripe)**: tông slate/zinc, viền 1px, không gradient/glow |
| **Testing** | pytest + pytest-asyncio + httpx ASGITransport (SQLite in-memory), 10 file test |

```text
detect-ai/
├── backend/
│   ├── sql/                      # 01_schema.sql (DDL), 02_seed.sql (dữ liệu mẫu),
│   │                             # 03_migrate_existing_db.sql (nâng cấp CSDL cũ),
│   │                             # 04_face_tables.sql (face_embeddings + face_events cho kiosk)
│   ├── src/detect_ai/
│   │   ├── ai/                   # YOLO26, tracker, InsightFace face_runtime, spoof, kiosk_pipeline
│   │   ├── api/                  # routes_auth, routes_teacher, routes_kiosk, routes_admin_*, ...
│   │   ├── core/                 # config, database, security, supabase, deps
│   │   ├── models/               # SQLAlchemy 2.0 models (11 bảng)
│   │   ├── services/             # evaluation, report, storage, settings_repo
│   │   └── main.py               # FastAPI app + APScheduler (cron 23h59)
│   └── tests/                    # 10 file test (unit + E2E) — 85 test
├── frontend/
│   └── app/                      # /login, /student/*, /teacher/*, /admin/*
└── docs/
    ├── DATABASE_SETUP_GUIDE.md   # Hướng dẫn cấu hình Supabase
    └── superpowers/              # spec & plan triển khai
```

---

## 3. Cài đặt & Khởi chạy

### 3.1 Yêu cầu
- Python **3.12+** ([uv](https://docs.astral.sh/uv/) khuyến nghị)
- Node.js **20+**
- (Tuỳ chọn) Project Supabase — xem [docs/DATABASE_SETUP_GUIDE.md](docs/DATABASE_SETUP_GUIDE.md)

### 3.2 Backend (FastAPI)

```bash
cd backend
uv sync                                   # cài dependency
cp .env.example .env                      # rồi điền thông tin Supabase (nếu dùng cloud)
uv run uvicorn detect_ai.main:app --reload --port 8000
```

> `backend/.env` được nạp tự động. Điền **đủ 4 biến** `DETECT_AI_SUPABASE_*` để chạy hoàn toàn trên
> Supabase; để trống thì backend dùng SQLite tại `backend/data/detect_ai.db`.
>
> **Chẩn đoán toàn diện** (khuyến nghị chạy trước khi tin là đã chuyển sang Supabase):
> ```bash
> uv run python -m detect_ai.doctor     # hoặc: uv run detect-ai-doctor
> ```
> Kiểm tra `.env`, chế độ CSDL, kết nối, đủ 11 bảng, cột `status`, pgvector, và 2 bucket Storage.
> Xem thêm [docs/DATABASE_SETUP_GUIDE.md §8.4](docs/DATABASE_SETUP_GUIDE.md).

- API docs: <http://localhost:8000/docs> — Health check: `GET /api/health` — Metrics: `/metrics`
- **Không cấu hình Supabase** ⇒ backend tự chạy SQLite tại `backend/data/detect_ai.db` và lưu file vào `backend/data/storage/`.

### 3.3 Frontend (Next.js)

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API=http://localhost:8000" > .env.local
npm run dev                               # http://localhost:3000
```

### 3.4 Tài khoản demo (sau khi chạy `02_seed.sql`)

| Vai trò | Mã đăng nhập | Mật khẩu | Trang mặc định |
| --- | --- | --- | --- |
| Quản trị viên | `ADMIN01` | `123456` | `/admin/users` |
| Giảng viên | `GV01` | `123456` | `/teacher/classes` |
| Sinh viên | `SV2026001` | `123456` | `/student/schedule` |

### 3.5 Sơ đồ màn hình

| Đường dẫn | Mô tả |
| --- | --- |
| `/login` | Đăng nhập bằng `user_code` + mật khẩu |
| `/student/schedule` · `/student/attendance` · `/student/conduct-points` · `/student/leave-requests` | Portal Sinh viên |
| `/teacher/classes` · `/teacher/classes/[id]/live` · `/teacher/classes/[id]/kiosk` · `/teacher/leave-reviews` · `/teacher/reports` | Portal Giảng viên |
| `/admin/users` · `/admin/academic` · `/admin/settings` · `/admin/reports` | Portal Quản trị |

---

## 4. Quy tắc nghiệp vụ cốt lõi

### 4.1 Thang điểm chuyên cần (cấu hình tại `/admin/settings`)
| Mã cấu hình | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `POINT_FULL_ATTENDANCE` | `+2` | Đủ check-in & check-out, đúng giờ, đủ đồng phục |
| `POINT_LATE` | `-1` | Đi muộn quá `LATE_TOLERANCE_MINUTES` (mặc định 15 phút) |
| `POINT_HALF_ABSENCE` | `-2` | Thiếu check-out khi `REQUIRE_CHECKOUT=true` |
| `POINT_ABSENCE_WITHOUT_LEAVE` | `-5` | Vắng không phép |
| `POINT_UNIFORM_VIOLATION` | `-2` | Vi phạm đồng phục (trừ thêm) |
| `CHECKOUT_MIN_GAP_MINUTES` | `5` | Phút tối thiểu giữa check-in và check-out (0 = cho out ngay) |
| `MAX_ABSENCE_PERCENT_EXAM_BAN` | `20` | Ngưỡng % vắng cả kỳ ⇒ cấm thi |

- Mọi biến động điểm **bắt buộc** đi qua sổ cái `point_ledger`; `student_profiles.total_point` là tổng hợp từ sổ cái và **không âm** (`MAX(0, ...)`).

### 4.2 Đánh giá tự động 23h59 (Idempotent)
- APScheduler chạy hằng ngày lúc **23:59 giờ Việt Nam** (`Asia/Ho_Chi_Minh`, không phụ thuộc múi giờ server); Admin có thể chạy bù qua `POST /api/v1/admin/evaluation/run-now`.
- Chỉ xử lý bản ghi `is_evaluated = FALSE` ⇒ chạy lại **không trừ điểm hai lần**.
- Tôn trọng tuyệt đối cờ `is_manual_override = TRUE` do giảng viên sửa tay.
- Đơn nghỉ phép đã duyệt ⇒ `EXCUSED`, `point_delta = 0`.

### 4.3 Hoàn điểm khi duyệt đơn muộn (Late Approval Refund)
- Nếu buổi học **đã bị Cron trừ điểm** rồi mới được duyệt đơn, hệ thống tự ghi bút toán hoàn điểm
  (`reason_code = 'LEAVE_REFUND'`, `point_delta = +` tổng điểm đã trừ) và cộng trả vào `total_point`.
- Có kiểm tra chống hoàn điểm trùng lặp cho cùng một buổi học.

### 4.4 Công thức cấm thi
- Hệ số quy đổi: `V = N_vắng + 0.5 × N_vắng_nửa_buổi` (buổi `EXCUSED` không tính).
- **Buổi "đã diễn ra"** = buổi đã **kết thúc** theo giờ Việt Nam. Buổi hôm nay chưa tới/chưa tan
  **không** được tính — nếu tính thì mọi sinh viên đều bị coi là vắng buổi đó và có thể bị cấm thi oan.
- Buổi đã kết thúc mà **không có bản ghi điểm danh** ⇒ tính là vắng không phép.
- **Cảnh báo lũy kế:** `V / N_buổi_đã_kết_thúc × 100% ≥ WARNING_ABSENCE_PERCENT` (mặc định `15`).
- **Cấm thi chính thức:** `V / classes.total_sessions × 100% ≥ MAX_ABSENCE_PERCENT_EXAM_BAN`
  (mặc định `20`) → xuất hiện trong báo cáo & file Excel cấm thi.
- Hai ngưỡng nhận **số thập phân** (VD `12.5`); `PUT /api/v1/admin/settings` từ chối giá trị không
  phải số hoặc ngoài khoảng `0–100` bằng HTTP `422`.

### 4.5 Ràng buộc an toàn & bảo mật
- **Chống trùng phòng:** không cho phép 2 lịch học cùng phòng, cùng ngày, chồng lấn thời gian.
- **Minh chứng nghỉ phép:** chỉ nhận `image/jpeg`, `image/png`, `application/pdf` và ≤ 5MB.
- **RBAC:** JWT + `require_role()`.

---

## 5. Kiểm thử

```bash
cd backend
uv run pytest tests -v                    # Toàn bộ test suite
uv run pytest tests/test_e2e_flow.py -v   # Riêng bộ E2E 5 kịch bản nghiệp vụ
```

Bộ test **E2E** (`backend/tests/test_e2e_flow.py`) đi qua đúng các HTTP endpoint thật trên một CSDL duy nhất:

1. Đi học đúng giờ + đủ đồng phục ⇒ Cron cộng **+2** điểm.
2. Quên check-out ⇒ Cron đánh **vắng nửa buổi, -2** điểm.
3. Nghỉ có phép (duyệt trước 23h59) ⇒ **EXCUSED, 0** điểm.
4. Duyệt đơn muộn sau 23h59 ⇒ hệ thống **hoàn điểm** tự động (`LEAVE_REFUND`).
5. Vắng ≥ 20% số buổi ⇒ xuất hiện trong **danh sách cấm thi** và **file Excel** (Giảng viên & Admin).

Ngoài ra còn kiểm thử: ma trận RBAC, tính Idempotent của Cron và **bất biến sổ cái**
(`Σ point_delta = total_point - 100`).

---

## 6. Tài liệu

- **Hướng dẫn cấu hình Supabase:** [docs/DATABASE_SETUP_GUIDE.md](docs/DATABASE_SETUP_GUIDE.md)
- **Spec thiết kế:** [docs/superpowers/specs/2026-09-16-smart-classroom-management-system-design.md](docs/superpowers/specs/2026-09-16-smart-classroom-management-system-design.md)
- **Kế hoạch triển khai (13 task):** [docs/superpowers/plans/2026-09-17-smart-classroom-system.md](docs/superpowers/plans/2026-09-17-smart-classroom-system.md)
- **API tương tác:** <http://localhost:8000/docs> (Swagger UI)

---

## 7. Ghi chú triển khai

- Đổi `DETECT_AI_JWT_SECRET` trước khi chạy thật; đổi mật khẩu 3 tài khoản seed.
- Cron 23h59 chỉ chạy khi tiến trình Backend còn sống — nên chạy dưới `systemd` / `pm2` / Docker restart-always.
- Model YOLO26 huấn luyện đồng phục đặt tại `backend/data/weights/uniform_yolo26.pt`; nếu thiếu, hệ thống fallback `yolo26n.pt`.
- **YOLO ONNX (khuyến nghị):** export 1 lần để inference nhanh hơn (~1.5x trên CPU) —
  `cd backend && uv run python -m detect_ai.ai.export_yolo_onnx` → ra `backend/data/weights/yolo26n.onnx`
  (FP32, imgsz 384, opset 19). App tự ưu tiên `.onnx` trước `.pt`, tự nhận diện phần cứng
  (CUDA/TensorRT/DirectML/CoreML/OpenVINO/CPU) để chọn provider/imgsz/threads; ép tay bằng
  `DETECT_AI_YOLO_PROVIDER`, `DETECT_AI_YOLO_IMGSZ`, `DETECT_AI_YOLO_THREADS` trong `backend/.env`.
  Kiểm parity + latency: `uv run python -m detect_ai.ai.bench_yolo_onnx`. File `.onnx` nằm trong
  `backend/data/` (đã gitignore) nên mỗi máy deploy tự export 1 lần.

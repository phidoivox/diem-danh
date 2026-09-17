# Hướng dẫn Thiết lập Cơ sở dữ liệu Supabase

> Tài liệu vận hành cho **Hệ thống Quản lý Lớp học Thông minh** (Smart Classroom Management System).
> Áp dụng cho Backend FastAPI + SQLAlchemy 2.0 Async (Cách 2: tách `users` và `student_profiles` / `teacher_profiles`).

---

## 1. Kiến trúc lưu trữ

| Thành phần | Vai trò |
| --- | --- |
| **Supabase PostgreSQL** | CSDL quan hệ 11 bảng: `roles`, `users`, `student_profiles`, `teacher_profiles`, `classes`, `class_students`, `schedules`, `attendance`, `leave_requests`, `point_ledger`, `system_settings` |
| **Supabase Storage** | 3 bucket: `leave-proofs` (minh chứng đơn nghỉ phép), `avatars` (ảnh chân dung), `snapshots` (ảnh điểm danh) |
| **Backend FastAPI** | Kết nối qua `asyncpg`, tự động `create_all` khi khởi động (`init_db()`) |
| **Chế độ Offline** | Nếu chưa cấu hình Supabase, backend tự fallback sang SQLite (`backend/data/detect_ai.db`) và lưu file vào `backend/data/storage/...` |

> **Lưu ý:** `init_db()` chỉ tạo bảng còn thiếu. Để có **ENUM, INDEX chống trùng phòng, seed data và comment đầy đủ**, hãy chạy 2 script SQL bên dưới trên Supabase.

---

## 2. Chuẩn bị

- Tài khoản [Supabase](https://supabase.com) (gói Free là đủ cho môi trường demo/học tập).
- Python **3.12+** và [uv](https://docs.astral.sh/uv/) (hoặc `pip`).
- Node.js **20+** cho Frontend Next.js.

---

## 3. Bước 1 — Tạo Project trên Supabase

1. Truy cập <https://supabase.com/dashboard> → **New project**.
2. Điền:
   - **Name:** `smart-classroom` (hoặc tên bất kỳ).
   - **Database Password:** mật khẩu mạnh — **lưu lại ngay**, cần cho chuỗi kết nối.
   - **Region:** `Southeast Asia (Singapore)` để giảm độ trễ.
3. Chờ 1–2 phút cho project khởi tạo xong.

---

## 4. Bước 2 — Lấy thông tin kết nối

Vào **Project Settings → API** lấy:

| Thông số | Vị trí | Biến môi trường |
| --- | --- | --- |
| Project URL | Project URL | `DETECT_AI_SUPABASE_URL` |
| `anon` public key | Project API keys | `DETECT_AI_SUPABASE_KEY` |
| `service_role` secret key | Project API keys (⚠️ bí mật) | `DETECT_AI_SUPABASE_SERVICE_KEY` |

Vào **Project Settings → Database → Connection string → Session pooler** (hoặc Direct connection) lấy chuỗi PostgreSQL:

```text
postgresql://postgres.xxxxxxxxxxxx:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
```

> Backend tự động đổi `postgresql://` → `postgresql+asyncpg://`, bạn **dán nguyên chuỗi gốc** vào `DETECT_AI_SUPABASE_DB_URL` là đủ.
> Nếu mật khẩu chứa ký tự đặc biệt (`@`, `#`, `%`...), hãy URL-encode trước khi dán.

---

## 5. Bước 3 — Chạy DDL Schema (`backend/sql/01_schema.sql`)

1. Mở **SQL Editor → New query**.
2. Dán toàn bộ nội dung file [`backend/sql/01_schema.sql`](../backend/sql/01_schema.sql) → **Run**.
3. Script tạo:
   - **ENUM:** `attendance_status` (`PRESENT`, `LATE`, `HALF_ABSENT`, `ABSENT`, `EXCUSED`), `leave_status` (`PENDING`, `APPROVED`, `REJECTED`), `user_role` (`ADMIN`, `TEACHER`, `STUDENT`).
   - **11 bảng** quan hệ chuẩn 3NF, có `deleted_at` (soft delete) trên `users`.
   - **Ràng buộc & Index** quan trọng: `uq_attendance_schedule_student`, `check_schedule_time_valid` (`start_time < end_time`), `idx_schedules_room_conflict` (chống trùng phòng học), `idx_attendance_evaluated` (phục vụ Cron 23h59 idempotent).
4. Kiểm tra: **Table Editor** phải hiển thị đủ 11 bảng.

---

## 6. Bước 4 — Nạp dữ liệu mẫu (`backend/sql/02_seed.sql`)

1. Trong **SQL Editor**, dán nội dung [`backend/sql/02_seed.sql`](../backend/sql/02_seed.sql) → **Run**.
2. Script chèn Roles + 3 tài khoản demo + 1 lớp học phần + bộ tham số `system_settings` mặc định:

| Vai trò | Mã đăng nhập (`user_code`) | Mật khẩu |
| --- | --- | --- |
| Quản trị viên | `ADMIN01` | `123456` |
| Giảng viên | `GV01` | `123456` |
| Sinh viên | `SV2026001` | `123456` |

> Script dùng `ON CONFLICT ... DO NOTHING/UPDATE` nên **chạy lại nhiều lần vẫn an toàn** (idempotent).
> ⚠️ Hãy đổi mật khẩu các tài khoản này trước khi triển khai thật.

---

## 7. Bước 5 — Tạo Storage Buckets

Vào **Storage → New bucket**, tạo lần lượt 3 bucket:

| Bucket | Mục đích | Chế độ |
| --- | --- | --- |
| `leave-proofs` | Ảnh/PDF minh chứng đơn xin nghỉ phép | Public |
| `avatars` | Ảnh chân dung sinh viên / giảng viên | Public |
| `snapshots` | Ảnh snapshot lúc điểm danh (đối soát trực quan) | Public |

Hoặc chạy nhanh trong **SQL Editor**:

```sql
-- 1. Tạo bucket (public = true để hiển thị ảnh qua URL công khai)
insert into storage.buckets (id, name, public) values
    ('leave-proofs', 'leave-proofs', true),
    ('avatars',      'avatars',      true),
    ('snapshots',    'snapshots',    true)
on conflict (id) do update set public = excluded.public;

-- 2. Cho phép đọc công khai (phục vụ hiển thị ảnh minh chứng / avatar trên Portal)
drop policy if exists "public_read_leave_proofs" on storage.objects;
create policy "public_read_leave_proofs" on storage.objects
    for select using (bucket_id in ('leave-proofs', 'avatars', 'snapshots'));

-- 3. Chỉ service_role (Backend) được ghi/xoá
drop policy if exists "service_role_write_objects" on storage.objects;
create policy "service_role_write_objects" on storage.objects
    for all to service_role using (true) with check (true);
```

> Backend upload bằng **service_role key** nên bỏ qua RLS. Nếu bucket để **Private**, hãy dùng *Signed URL* khi hiển thị ảnh.

---

## 8. Bước 6 — Cấu hình biến môi trường

### 8.1 Backend — `backend/.env`

Sao chép `backend/.env.example` thành `backend/.env` rồi điền:

```dotenv
# ===== Supabase =====
DETECT_AI_SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
DETECT_AI_SUPABASE_KEY=eyJhbGciOi...            # anon public key
DETECT_AI_SUPABASE_SERVICE_KEY=eyJhbGciOi...    # service_role key (BÍ MẬT)
DETECT_AI_SUPABASE_DB_URL=postgresql://postgres.xxxx:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres

# ===== Bảo mật =====
DETECT_AI_JWT_SECRET=doi-thanh-chuoi-ngau-nhien-dai-32-ky-tu
DETECT_AI_KIOSK_API_KEY=kiosk-secret-key-2026

# ===== AI Engine (tuỳ chọn) =====
DETECT_AI_FACE_SIM_THRESHOLD=0.55
DETECT_AI_YOLO_CONF=0.35
DETECT_AI_YOLO_IMGSZ=384
DETECT_AI_REQUIRE_ID_CARD=true
DETECT_AI_LIVENESS=true
```

### 8.2 Frontend — `frontend/.env.local`

```dotenv
NEXT_PUBLIC_API=http://localhost:8000
```

### 8.3 Bảng biến môi trường đầy đủ

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `DETECT_AI_SUPABASE_DB_URL` | *(rỗng)* | Chuỗi kết nối PostgreSQL. **Ưu tiên cao nhất**; rỗng ⇒ dùng SQLite |
| `DETECT_AI_DATABASE_URL` | `sqlite+aiosqlite:///backend/data/detect_ai.db` | CSDL dự phòng khi chạy offline |
| `DETECT_AI_SUPABASE_URL` | *(rỗng)* | Project URL — rỗng ⇒ lưu file xuống đĩa local |
| `DETECT_AI_SUPABASE_SERVICE_KEY` | *(rỗng)* | Key ghi Storage (`service_role`) |
| `DETECT_AI_JWT_SECRET` | chuỗi demo | Khoá ký JWT — **phải đổi khi triển khai** |
| `DETECT_AI_KIOSK_API_KEY` | `kiosk-secret-key-2026` | API key cho thiết bị Kiosk (`X-Kiosk-Api-Key`) |

> Ngưỡng trễ, thang điểm và tỷ lệ cấm thi **không** đặt qua ENV mà nằm trong bảng `system_settings` (chỉnh tại `/admin/settings`).

---

## 9. Bước 7 — Khởi động & kiểm tra

```bash
# 1. Cài đặt & chạy Backend
cd backend
uv sync                      # hoặc: python -m venv .venv && .venv/Scripts/pip install -e .
uv run uvicorn detect_ai.main:app --reload --port 8000

# 2. Kiểm tra kết nối
curl http://localhost:8000/api/health          # -> {"ok": true}

# 3. Đăng nhập thử tài khoản Admin
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_code": "ADMIN01", "password": "123456"}'

# 4. Chạy Frontend
cd ../frontend
npm install
npm run dev                   # http://localhost:3000
```

**Checklist xác nhận Supabase đã nối đúng:**

- [ ] `GET /api/health` trả `{"ok": true}` và log khởi động **không** báo lỗi `asyncpg`.
- [ ] Đăng nhập `ADMIN01 / 123456` thành công, `GET /api/v1/auth/me` trả đúng role `ADMIN`.
- [ ] Bảng `users` trên Supabase có thêm bản ghi khi tạo người dùng mới từ `/admin/users`.
- [ ] Upload minh chứng từ `/student/leave-requests` ⇒ file xuất hiện trong bucket `leave-proofs`.
- [ ] `POST /api/v1/admin/evaluation/run-now` trả về `total_records` và sinh bản ghi trong `point_ledger`.

---

## 10. Chế độ phát triển Offline (không cần Supabase)

Bỏ trống `DETECT_AI_SUPABASE_DB_URL` và `DETECT_AI_SUPABASE_URL`, backend sẽ:

- Dùng SQLite tại `backend/data/detect_ai.db` (bật WAL + `PRAGMA foreign_keys=ON`).
- Tự tạo toàn bộ bảng qua `Base.metadata.create_all` khi khởi động.
- Lưu file minh chứng vào `backend/data/storage/<bucket>/...` và trả URL dạng `/static/storage/leave-proofs/<file>`.

> Chế độ này dùng cho **phát triển & chạy test** (`pytest` dùng SQLite in-memory). Dữ liệu SQLite **không** đồng bộ lên Supabase.

---

## 11. Xử lý sự cố thường gặp

| Triệu chứng | Nguyên nhân & cách xử lý |
| --- | --- |
| `invalid DSN: invalid sslmode value` | Chuỗi kết nối chứa `?sslmode=...` không hợp lệ với asyncpg → xoá tham số khỏi URL |
| `password authentication failed` | Sai/thiếu URL-encode mật khẩu trong `DETECT_AI_SUPABASE_DB_URL` |
| `type "attendance_status" does not exist` | Chưa chạy `01_schema.sql`, hoặc chạy trên schema khác `public` |
| Upload minh chứng lỗi 500 | Sai `DETECT_AI_SUPABASE_SERVICE_KEY`, bucket chưa tạo, hoặc tên bucket khác `leave-proofs` |
| Ảnh minh chứng không hiển thị | Bucket đang **Private** → đổi sang Public hoặc dùng Signed URL |
| Đăng nhập báo "Tài khoản hoặc mật khẩu không đúng" | Chưa chạy `02_seed.sql`, hoặc `user_code` viết sai (phân biệt hoa/thường) |
| Cron 23h59 không chạy | Backend phải chạy liên tục; kiểm tra log `Nightly evaluation cron scheduled for 23:59` |
| Test suite báo lỗi kết nối DB | `pytest` không cần Supabase — kiểm tra biến môi trường có vô tình trỏ vào DB thật không |

---

## 12. Tham chiếu

- Spec thiết kế: [docs/superpowers/specs/2026-09-16-smart-classroom-management-system-design.md](superpowers/specs/2026-09-16-smart-classroom-management-system-design.md)
- Kế hoạch triển khai: [docs/superpowers/plans/2026-09-17-smart-classroom-system.md](superpowers/plans/2026-09-17-smart-classroom-system.md)
- Hướng dẫn vận hành tổng thể: [README.md](../README.md)

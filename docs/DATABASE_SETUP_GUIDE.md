# Hướng dẫn Thiết lập Cơ sở dữ liệu Supabase

> Tài liệu vận hành cho **Hệ thống Quản lý Lớp học Thông minh** (Smart Classroom Management System).
> Áp dụng cho Backend FastAPI + SQLAlchemy 2.0 Async (Cách 2: tách `users` và `student_profiles` / `teacher_profiles`).

---

## 1. Kiến trúc lưu trữ

| Thành phần | Vai trò |
| --- | --- |
| **Supabase PostgreSQL** | CSDL quan hệ 11 bảng: `roles`, `users`, `student_profiles`, `teacher_profiles`, `classes`, `class_students`, `schedules`, `attendance`, `leave_requests`, `point_ledger`, `system_settings` |
| **Supabase Storage** | 2 bucket: `leave-proofs` (minh chứng đơn nghỉ phép), `avatars` (ảnh chân dung) |
| **Backend FastAPI** | Kết nối qua `asyncpg`, tự động `create_all` khi khởi động (`init_db()`) |
| **Chế độ Offline** | Nếu chưa cấu hình Supabase, backend tự fallback sang SQLite (`backend/data/detect_ai.db`) và lưu file vào `backend/data/storage/...` |

> **Lưu ý:** `init_db()` chỉ tạo bảng còn thiếu, **không ALTER bảng đã tồn tại**. Để có **CHECK constraint, INDEX chống trùng phòng, seed data và comment đầy đủ**, hãy chạy các script SQL trong `backend/sql/` trên Supabase.
>
> **Nếu project Supabase của bạn đã tạo từ bản cũ** (bản còn `CREATE TYPE ... AS ENUM`), hãy chạy thêm
> [`backend/sql/03_migrate_existing_db.sql`](../backend/sql/03_migrate_existing_db.sql) — xem §5b.

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
   - **11 bảng** quan hệ chuẩn 3NF, có `deleted_at` (soft delete) trên `users`.
   - **Trạng thái dạng `VARCHAR + CHECK`** (không dùng ENUM native):
     `CONSTRAINT attendance_status CHECK (status IN ('PRESENT','LATE','HALF_ABSENT','ABSENT','EXCUSED'))`,
     `CONSTRAINT leave_status CHECK (status IN ('PENDING','APPROVED','REJECTED'))`.
     Lý do: ORM khai `native_enum=False` nên nếu file SQL tạo ENUM native thì hai đường tạo bảng
     (chạy SQL vs để `init_db()` tự `create_all`) sẽ cho ra hai schema vật lý khác nhau.
   - **Ràng buộc & Index** quan trọng: `uq_attendance_schedule_student`,
     `check_schedule_time_valid` (`start_time < end_time`),
     `idx_schedules_room_conflict` (chống trùng phòng học),
     `idx_attendance_evaluated` (phục vụ Cron 23h59 idempotent),
     `uq_leave_requests_active` (chống nộp trùng đơn nghỉ phép khi có request đồng thời).
4. Kiểm tra: **Table Editor** phải hiển thị đủ 11 bảng.
5. **Điểm danh khuôn mặt (Kiosk):** dán tiếp nội dung
   [`backend/sql/04_face_tables.sql`](../backend/sql/04_face_tables.sql) → **Run**
   (tạo thêm `face_embeddings` + `face_events`, idempotent — CSDL cũ cũng chạy file này).

---

## 5b. Bước 3b — (Chỉ khi nâng cấp) Migration CSDL đã tồn tại

**Bỏ qua mục này nếu bạn vừa tạo project Supabase mới.**

Nếu project đã chạy `01_schema.sql` **bản cũ**, cột `attendance.status` và `leave_requests.status`
đang là ENUM native của Postgres. ORM lại gửi tham số dạng text nên `asyncpg` có thể báo:

```text
column "status" is of type attendance_status but expression is of type text
```

Cách xử lý: mở **SQL Editor**, dán nội dung
[`backend/sql/03_migrate_existing_db.sql`](../backend/sql/03_migrate_existing_db.sql) → **Run**.

Script này (idempotent, chạy lại vẫn an toàn):

1. Chuyển `attendance.status` → `VARCHAR(11)` + CHECK `attendance_status`.
2. Chuyển `leave_requests.status` → `VARCHAR(8)` + CHECK `leave_status`.
3. Xoá các ENUM type không còn dùng (`attendance_status`, `leave_status`, `user_role`).
4. Tạo `uq_leave_requests_active`. **Nếu đang có dữ liệu trùng** (cùng `schedule_id` + `student_id`
   mà có ≥ 2 đơn `PENDING`/`APPROVED`), script sẽ dừng và báo rõ số cặp trùng để bạn xử lý tay trước.
5. (Tuỳ chọn, mặc định **bị comment**) xoá 3 bảng của lớp legacy đã bỏ khỏi mã nguồn:
   `legacy_attendance`, `uniform_rules`, `students`.

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

Vào **Storage → New bucket**, tạo lần lượt 2 bucket:

| Bucket | Mục đích | Chế độ |
| --- | --- | --- |
| `leave-proofs` | Ảnh/PDF minh chứng đơn xin nghỉ phép | Public |
| `avatars` | Ảnh chân dung sinh viên / giảng viên | Public |

> Bucket `snapshots` không còn cần thiết: ảnh snapshot trước đây do `save_queue` sinh ra
> chỉ để phục vụ trang `/attendance` — cả hai đã bị xoá cùng lớp legacy.

Hoặc chạy nhanh trong **SQL Editor**:

```sql
-- 1. Tạo bucket (public = true để hiển thị ảnh qua URL công khai)
insert into storage.buckets (id, name, public) values
    ('leave-proofs', 'leave-proofs', true),
    ('avatars',      'avatars',      true)
on conflict (id) do update set public = excluded.public;

-- 2. Cho phép đọc công khai (phục vụ hiển thị ảnh minh chứng / avatar trên Portal)
drop policy if exists "public_read_leave_proofs" on storage.objects;
create policy "public_read_leave_proofs" on storage.objects
    for select using (bucket_id in ('leave-proofs', 'avatars'));

-- 3. Chỉ service_role (Backend) được ghi/xoá
drop policy if exists "service_role_write_objects" on storage.objects;
create policy "service_role_write_objects" on storage.objects
    for all to service_role using (true) with check (true);
```

> Backend upload bằng **service_role key** nên bỏ qua RLS. Nếu bucket để **Private**, hãy dùng *Signed URL* khi hiển thị ảnh.

---

## 8. Bước 6 — Cấu hình biến môi trường

### 8.1 Backend — `backend/.env`

Sao chép `backend/.env.example` thành `backend/.env` rồi điền.

> `backend/.env` được **nạp tự động** khi khởi động (đường dẫn tuyệt đối, không phụ thuộc thư mục
> chạy lệnh). Nếu bạn đặt biến môi trường ở nơi khác (Docker, systemd, CI), biến môi trường thật
> **ghi đè** file `.env`.

```dotenv
# ===== Supabase =====
DETECT_AI_SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
DETECT_AI_SUPABASE_KEY=eyJhbGciOi...            # anon public key
DETECT_AI_SUPABASE_SERVICE_KEY=eyJhbGciOi...    # service_role key (BÍ MẬT)
DETECT_AI_SUPABASE_DB_URL=postgresql://postgres.xxxx:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres

# ===== Bảo mật =====
DETECT_AI_JWT_SECRET=doi-thanh-chuoi-ngau-nhien-dai-32-ky-tu

# ===== AI Engine (tuỳ chọn) =====
DETECT_AI_YOLO_CONF=0.35
DETECT_AI_YOLO_IMGSZ=384
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

> Ngưỡng trễ, thang điểm và tỷ lệ cấm thi **không** đặt qua ENV mà nằm trong bảng `system_settings` (chỉnh tại `/admin/settings`).

### 8.4 Chuyển hẳn sang Supabase — checklist

**Bước 1 — Chọn chuỗi kết nối** (Supabase → Project Settings → Database → Connection string):

| Kiểu | Host / Cổng | Khi nào dùng |
| --- | --- | --- |
| **Session pooler** *(khuyến nghị)* | `aws-0-<region>.pooler.supabase.com:5432` | Hợp với 1 tiến trình backend. Giữ được prepared statement nên nhanh nhất |
| **Transaction pooler** | `aws-0-<region>.pooler.supabase.com:6543` | Khi chạy nhiều worker/instance. Backend **tự động** tắt prepared statement cache cho cổng 6543 |
| Direct connection | `db.<ref>.supabase.co:5432` | Project mới **chỉ có IPv6** — nếu mạng không hỗ trợ IPv6 thì phải dùng pooler |

Backend tự nhận biết và cấu hình `asyncpg` tương ứng: ép SSL cho host Supabase, và đặt
`statement_cache_size=0` khi thấy cổng `6543` (nếu không sẽ gặp lỗi
`prepared statement "__asyncpg_stmt_1__" already exists`).

**Bước 2 — Tắt tự tạo bảng.** Đặt trong `backend/.env`:

```dotenv
DETECT_AI_AUTO_CREATE_TABLES=false
```

Để `true` thì `create_all` và các file `backend/sql/` cùng sở hữu schema → quay lại đúng cái drift
hai nguồn sự thật mà dự án từng dính. Trên Supabase, **schema chỉ nên do `backend/sql/` sở hữu**.

**Bước 3 — Chạy chẩn đoán:**

```bash
cd backend
uv run python -m detect_ai.doctor     # hoặc: uv run detect-ai-doctor
```

Công cụ kiểm tra và báo `[ OK ]` / `[WARN]` / `[FAIL]` cho:

- `.env` có tồn tại và được nạp không; đang chạy SQLite hay Supabase
- `DETECT_AI_JWT_SECRET` còn là giá trị demo không
- Kết nối CSDL + phiên bản server
- Đủ 11 bảng chưa; cột `status` đúng dạng `VARCHAR` chưa (phát hiện ENUM native còn sót)
- Supabase Storage đã bật chưa và 2 bucket `leave-proofs`, `avatars` có chưa

Thoát mã `0` nếu không có lỗi chặn, `1` nếu còn `[FAIL]`.

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
| `column "status" is of type attendance_status but expression is of type text` | CSDL tạo từ `01_schema.sql` bản cũ (ENUM native). Chạy `backend/sql/03_migrate_existing_db.sql` — xem §5b |
| `type "attendance_status" does not exist` | Bạn đang chạy bản SQL cũ trên CSDL mới. Dùng `01_schema.sql` hiện tại (VARCHAR + CHECK) |
| Ảnh minh chứng 404 dù file có trên đĩa | Chế độ offline: backend phải mount `/static/storage`; kiểm tra `GET /static/storage/leave-proofs/<file>` |
| Upload minh chứng lỗi 500 | Sai `DETECT_AI_SUPABASE_SERVICE_KEY`, bucket chưa tạo, hoặc tên bucket khác `leave-proofs` |
| Ảnh minh chứng không hiển thị | Bucket đang **Private** → đổi sang Public hoặc dùng Signed URL |
| Đăng nhập báo "Tài khoản hoặc mật khẩu không đúng" | Chưa chạy `02_seed.sql`, hoặc `user_code` viết sai (phân biệt hoa/thường) |
| `prepared statement "__asyncpg_stmt_1__" already exists` | Đang dùng transaction pooler (cổng 6543) — bản cũ chưa tắt statement cache. Bản hiện tại tự xử lý; nếu vẫn gặp, kiểm tra URL có đúng cổng `6543` |
| `server does not support SSL` | URL trỏ tới Postgres tự dựng nhưng bị nhận nhầm là Supabase. Backend chỉ ép SSL khi host chứa `supabase` |
| **Đã điền `.env` mà backend vẫn dùng SQLite** | Kiểm tra tên biến có đúng tiền tố `DETECT_AI_` không, và file phải nằm đúng `backend/.env`. Xác nhận nhanh: `uv run python -c "from detect_ai.core.config import DATABASE_URL; print(DATABASE_URL)"` — phải in ra `postgresql+asyncpg://...` |
| Cron 23h59 không chạy | Backend phải chạy liên tục; kiểm tra log `Nightly evaluation cron scheduled for 23:59` |
| Test suite báo lỗi kết nối DB | `pytest` không cần Supabase — kiểm tra biến môi trường có vô tình trỏ vào DB thật không |

---

## 12. Tham chiếu

- Spec thiết kế: [docs/superpowers/specs/2026-09-16-smart-classroom-management-system-design.md](superpowers/specs/2026-09-16-smart-classroom-management-system-design.md)
- Kế hoạch triển khai: [docs/superpowers/plans/2026-09-17-smart-classroom-system.md](superpowers/plans/2026-09-17-smart-classroom-system.md)
- Hướng dẫn vận hành tổng thể: [README.md](../README.md)

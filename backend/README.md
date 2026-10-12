# Backend - Detect AI (Hệ thống Quản lý & Điểm danh Lớp học Thông minh)

Backend dịch vụ cung cấp API RESTful & WebSocket phục vụ điểm danh thông minh bằng khuôn mặt (Kiosk), nhận diện đồng phục, quản lý đào tạo, đơn nghỉ phép, tính điểm rèn luyện tự động và báo cáo cấm thi.

---

## 1. Yêu cầu hệ thống

* **Hệ điều hành**: Linux (Ubuntu 20.04+), macOS, hoặc Windows 10/11
* **Python**: Phiên bản `>= 3.12` (khuyến nghị 3.12.x)
* **Trình quản lý gói**: [`uv`](https://docs.astral.sh/uv/) (khuyến nghị để cài đặt cực nhanh) hoặc `pip`
* **Cơ sở dữ liệu**:
  * **Môi trường phát triển cục bộ**: SQLite (`backend/data/detect_ai.db` - tự động tạo)
  * **Môi trường sản xuất / Production**: PostgreSQL / Supabase PostgreSQL (hỗ trợ pgvector cho face embeddings)

---

## 2. Hướng dẫn cài đặt nhanh

### Bước 1: Di chuyển vào thư mục backend
```bash
cd backend
```

### Bước 2: Thiết lập môi trường ảo và cài đặt thư viện

Sử dụng `uv` (Khuyến nghị):
```bash
uv sync
```

Hoặc sử dụng `python venv` và `pip`:
```bash
python -m venv .venv
# Trên Windows:
.venv\Scripts\activate
# Trên Linux/macOS:
source .venv/bin/activate

pip install -e .
```

### Bước 3: Cấu hình biến môi trường
Sao chép tệp mẫu và cập nhật các giá trị cấu hình:
```bash
cp .env.example .env
```
Các tham số cấu hình chính trong `.env`:
* `DETECT_AI_JWT_SECRET`: Khóa bí mật ký token JWT (bắt buộc đổi khi triển khai thực tế).
* `DETECT_AI_SUPABASE_DB_URL`: Để trống để chạy SQLite local, hoặc điền PostgreSQL URL để chạy production.
* `DETECT_AI_CORS_ORIGINS`: Danh sách domain frontend được phép gọi API (ví dụ: `http://localhost:3000`).
* `DETECT_AI_FACE_PACK`: Gói model InsightFace (`auto`, `buffalo_s` cho CPU hoặc `buffalo_l` cho GPU).

---

## 3. Khởi tạo Cơ sở dữ liệu

Khi sử dụng PostgreSQL / Supabase, thực thi các file SQL theo thứ tự trong thư mục `sql/`:
1. `backend/sql/01_schema.sql`: Khởi tạo bảng dữ liệu và quan hệ.
2. `backend/sql/02_seed.sql`: Nạp tài khoản quản trị và dữ liệu mẫu ban đầu.
3. `backend/sql/04_face_tables.sql` & `06_pgvector_gallery.sql`: Cấu hình lưu trữ embedding khuôn mặt.
4. `backend/sql/10_notifications.sql`: Bảng thông báo.
5. `backend/sql/11_default_point_95.sql`: Điểm rèn luyện khởi tạo.

*Lưu ý*: Với SQLite, ứng dụng sẽ tự động khởi tạo cấu trúc bảng khi khởi động nếu chưa có DB.

---

## 4. Khởi chạy Backend

### Chạy ở chế độ Development (Auto-reload):
```bash
uv run uvicorn detect_ai.main:app --host 0.0.0.0 --port 8000 --reload
```

### Chạy ở chế độ Production:
```bash
uv run uvicorn detect_ai.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Sau khi khởi chạy thành công:
* **API Root**: `http://localhost:8000/`
* **Swagger API Documentation**: `http://localhost:8000/docs`
* **ReDoc Documentation**: `http://localhost:8000/redoc`
* **Health Check**: `http://localhost:8000/health`

---

## 5. Kiểm thử & Đảm bảo chất lượng

### Chạy toàn bộ Test Suite (140+ test cases):
```bash
uv run pytest tests -v
```

### Kiểm tra ranh giới kiến trúc (Clean Architecture / Modular Monolith):
```bash
python scripts/check_bounds.py
```

---

## 6. Cấu trúc Mô-đun (Modular Monolith)

Mã nguồn được tổ chức theo kiến trúc Modular Monolith chuẩn sạch:
```text
backend/src/detect_ai/
├── modules/
│   ├── academic/       # Quản lý môn học, lớp học phần, phòng học, thời khóa biểu
│   ├── attendance/     # Điểm danh ca học, Kiosk nhận diện mặt, WebSocket camera
│   ├── evaluation/     # Sổ cái điểm rèn luyện (point ledger), cron tính điểm 23h59
│   ├── identity/       # Xác thực JWT, phân quyền Admin/Teacher/Student, CRUD user
│   ├── leave/          # Quy trình nộp và duyệt đơn xin nghỉ phép kèm minh chứng
│   ├── recognition/    # Pipeline AI (InsightFace, Anti-spoofing, YOLO Uniform)
│   └── reporting/      # Thống kê chuyên cần, xuất báo cáo cấm thi Excel
└── shared/
    ├── kernel/         # Database engine, base models, JWT helper, security, errors
    └── notifications/  # Dịch vụ thông báo nội bộ
```

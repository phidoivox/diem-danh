# Kế hoạch Triển khai: Hệ thống Quản lý Lớp học Thông minh (Smart Classroom Management System)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng hoàn chỉnh hệ thống Quản lý Lớp học Thông minh tích hợp Điểm danh AI (FaceID + Đồng phục + Check-in/out), 3 phân hệ Portal (Sinh viên, Giảng viên, Quản trị viên), luồng nộp và duyệt đơn nghỉ phép trực tuyến kèm minh chứng, công cụ tính điểm chuyên cần tự động 23h59 (Idempotent Cron & Point Ledger) và xuất báo cáo cấm thi chuẩn quy chế trên nền tảng Supabase.

**Architecture:** 
- **Database Tier:** Supabase PostgreSQL (9 bảng quan hệ chuẩn 3NF, Enums, Constraints, Soft-delete) + Supabase Storage (bucket `leave-proofs`, `avatars`).
- **Backend Tier:** FastAPI + Async SQLAlchemy (`asyncpg`) + Pydantic v2 + APScheduler (Cron 23h59) + JWT RBAC & Kiosk API Key + AI Engine (YOLO26, Supervision, InsightFace, Faiss in-memory).
- **Frontend Tier:** Next.js (App Router) + Tailwind CSS + Lucide Icons tuân thủ CRM Dashboard Design token system (Sidebar + Topbar, Data Tables, Stat Cards, Live Sĩ số, Modals).

**Tech Stack:** FastAPI, Python 3.12, Supabase PostgreSQL, Supabase Storage, SQLAlchemy 2.0 Async, PyJWT, Passlib (Bcrypt), APScheduler, OpenPyXL, Next.js 16, React 19, Tailwind CSS v4, Lucide-React.

**Spec:** `docs/superpowers/specs/2026-09-16-smart-classroom-management-system-design.md`

## Global Constraints
- `total_point` bản chất là Điểm Chuyên cần & Tác phong Học vụ (tính từ `point_ledger`).
- Mọi biến động điểm rèn luyện/chuyên cần PHẢI được ghi nhận qua sổ cái `point_ledger`.
- Ảnh chân dung gốc của sinh viên/giảng viên và ảnh snapshot lúc điểm danh VẪN ĐƯỢC LƯU TRỮ trên Supabase Storage (`avatars`, `snapshots`) để hiển thị và đối soát trực quan.
- **Phong cách Giao diện (UI/UX)**: Chuẩn **SaaS Quản lý (Enterprise Restraint)** theo phong cách Linear / Stripe Dashboard. Tuyệt đối không dùng gradient màu mè, không hiệu ứng glow neon AI, không bóng mờ phức tạp; dùng bảng màu trung tính (slate/zinc), đường viền 1px tinh gọn, màu sắc chỉ dùng cho ý nghĩa trạng thái (semantic), ưu tiên mật độ hiển thị thông tin cao, rõ ràng, dễ quét mắt.
- **Phân quyền Xuất Báo cáo Cấm thi**:
  - Giảng viên: Xuất báo cáo cấm thi của **từng môn học / lớp học phần** do mình phụ trách.
  - Quản trị viên (Admin): Xuất báo cáo cấm thi của **toàn trường** (hỗ trợ lọc theo khoa, học kỳ, môn học).
- Cron 23h59 PHẢI đảm bảo tính Idempotent (chỉ xử lý `is_evaluated = FALSE`, tôn trọng cờ `is_manual_override = TRUE`).
- Tuyệt đối không để lộ `face_embedding` qua các REST DTOs công khai (tuân thủ Nghị định 13/2023/NĐ-CP).
- File minh chứng đơn nghỉ phép chỉ chấp nhận MIME type: `image/jpeg`, `image/png`, `application/pdf` và kích thước $\le 5$MB.
- Ràng buộc chống trùng phòng học: Không được có 2 lịch học cùng phòng, cùng ngày có thời gian chồng lấn (`start_time < end_time`).

---

## Danh sách Task chi tiết

### Task 1: Thiết lập CSDL Supabase, DDL Script & SQLAlchemy 2.0 Async Models (Mô hình Cách 2)

**Files:**
- Create: `backend/src/detect_ai/core/supabase.py`
- Create: `backend/sql/01_schema.sql`
- Create: `backend/sql/02_seed.sql`
- Modify: `backend/src/detect_ai/core/config.py`
- Modify: `backend/src/detect_ai/core/database.py`
- Create: `backend/src/detect_ai/models/user.py`
- Create: `backend/src/detect_ai/models/academic.py`
- Create: `backend/src/detect_ai/models/attendance_v2.py`
- Create: `backend/src/detect_ai/models/leave_request.py`
- Create: `backend/src/detect_ai/models/point_ledger.py`
- Create: `backend/src/detect_ai/models/system_setting.py`
- Test: `backend/tests/test_db_models.py`

**Interfaces:**
- Consumes: Config settings (`SUPABASE_DB_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`)
- Produces: SQLAlchemy Models: `User`, `Role`, `StudentProfile`, `TeacherProfile`, `Class`, `ClassStudent`, `Schedule`, `Attendance`, `LeaveRequest`, `PointLedger`, `SystemSetting`

- [ ] **Step 1: Viết test kiểm tra khởi tạo schema và các model quan hệ theo Cách 2**
  - Viết file `backend/tests/test_db_models.py` kiểm tra khai báo các bảng: `users`, `student_profiles`, `teacher_profiles`, enums, relationship 1-1 và default values.
- [ ] **Step 2: Viết file SQL DDL (`backend/sql/01_schema.sql`) trên Supabase**
  - Bao gồm: enums `attendance_status`, `leave_status`, `user_role`.
  - Bảng `users` (định danh, auth), `student_profiles` (chứa `face_embedding`, `total_point`, `class_name`), `teacher_profiles` (chứa `department`, `academic_title`), `roles`, `classes`, `class_students`, `schedules`, `attendance`, `leave_requests`, `point_ledger`, `system_settings`.
  - Bao gồm Index chống trùng phòng và Index tra cứu theo `user_code`, `study_date`.
- [ ] **Step 3: Viết file Seed data (`backend/sql/02_seed.sql`)**
  - Chèn Roles (ADMIN, TEACHER, STUDENT), tài khoản Admin, Giảng viên mẫu (kèm `teacher_profiles`), Sinh viên mẫu (kèm `student_profiles` với mật khẩu hash `123456`), Cấu hình `system_settings` mặc định.
- [ ] **Step 4: Cập nhật config và khai báo SQLAlchemy models**
  - Hỗ trợ `DATABASE_URL` từ PostgreSQL (`postgresql+asyncpg://...`) với fallback tương thích.
  - Tạo các model mapped SQLAlchemy 2.0 đầy đủ quan hệ ForeignKey và 1-1 relationship giữa `User` và `StudentProfile` / `TeacherProfile`.
- [ ] **Step 5: Chạy test kiểm thử model**
  - Run: `pytest backend/tests/test_db_models.py -v`
  - Expected: PASS.

---

### Task 2: Xác thực Người dùng (Auth JWT), Phân quyền RBAC & Kiosk API Key

**Files:**
- Create: `backend/src/detect_ai/core/security.py`
- Create: `backend/src/detect_ai/api/routes_auth.py`
- Create: `backend/src/detect_ai/api/deps_auth.py`
- Modify: `backend/src/detect_ai/main.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `User` model, `password_hash`, secret key từ config
- Produces: 
  - `POST /api/v1/auth/login` -> `{ access_token, token_type, role, user }`
  - `GET /api/v1/auth/me` -> Thông tin user đăng nhập (không chứa `face_embedding`)
  - Dependencies: `get_current_user`, `require_role(role_name)`, `verify_kiosk_api_key`

- [x] **Step 1: Viết test failing cho xác thực và phân quyền RBAC**
  - Viết `backend/tests/test_auth.py` kiểm tra đăng nhập đúng/sai mật khẩu, mã hóa bcrypt, xác thực JWT, chặn sai role (403), chặn thiếu Kiosk API key (401).
- [x] **Step 2: Cài đặt module `security.py`**
  - Các hàm: `verify_password()`, `get_password_hash()`, `create_access_token()`, `decode_access_token()`.
- [x] **Step 3: Cài đặt dependencies `deps_auth.py`**
  - `get_current_user`: giải mã JWT và lấy user từ DB, kiểm tra `is_active=True` và `deleted_at IS NULL`.
  - `require_role(*roles)`: enforce vai trò người dùng (ADMIN, TEACHER, STUDENT).
  - `verify_kiosk_api_key`: kiểm tra header `X-Kiosk-Api-Key` khớp với cấu hình hệ thống.
- [x] **Step 4: Cài đặt router `routes_auth.py` và gắn vào `main.py`**
  - Endpoint `/api/v1/auth/login` và `/api/v1/auth/me`.
- [x] **Step 5: Chạy test xác thực**
  - Run: `pytest backend/tests/test_auth.py -v`
  - Expected: PASS.

---

### Task 3: Phân hệ Quản trị Học vụ (Admin Services & CRUD)

**Files:**
- Create: `backend/src/detect_ai/api/routes_admin_users.py`
- Create: `backend/src/detect_ai/api/routes_admin_academic.py`
- Create: `backend/src/detect_ai/api/routes_admin_settings.py`
- Modify: `backend/src/detect_ai/main.py`
- Test: `backend/tests/test_admin_academic.py`

**Interfaces:**
- Consumes: `require_role('ADMIN')`, `User`, `Class`, `Schedule`, `SystemSetting`
- Produces:
  - User CRUD: Sinh viên/Giảng viên (hỗ trợ soft delete, upload ảnh đại diện & sinh face vector).
  - Class & Student enrollment CRUD: Gán sinh viên vào lớp học phần.
  - Schedule CRUD: Thêm lịch học với validation chống trùng phòng (`room_name`, `study_date`, khoảng thời gian `start_time` - `end_time`).
  - System Settings: `GET / PUT /api/v1/admin/settings` đọc & lưu tham số tính điểm/trễ.

- [ ] **Step 1: Viết test cho nghiệp vụ Quản trị & kiểm tra chống trùng phòng**
  - Viết `backend/tests/test_admin_academic.py` kiểm thử thêm lớp, thêm sinh viên vào lớp, tạo lịch học (kỳ vọng ném lỗi 400 nếu trùng phòng), soft delete user (không mất điểm danh cũ).
- [ ] **Step 2: Cài đặt `routes_admin_users.py`**
  - Danh sách User (phân trang, search, lọc role), Tạo user mới, Cập nhật thông tin, Xóa mềm (`deleted_at = NOW()`).
  - Hỗ trợ endpoint trích xuất face embedding từ ảnh chân dung và lưu vào cột `face_embedding`.
- [ ] **Step 3: Cài đặt `routes_admin_academic.py`**
  - Quản lý Classes, Thêm/Xóa sinh viên vào lớp (`class_students`).
  - Quản lý Schedules: logic kiểm tra xung đột phòng học:
    `WHERE room_name = :room AND study_date = :date AND NOT (end_time <= :new_start OR start_time >= :new_end)`.
- [ ] **Step 4: Cài đặt `routes_admin_settings.py`**
  - CRUD tham số cấu hình: `POINT_FULL_ATTENDANCE`, `POINT_LATE`, `POINT_HALF_ABSENCE`, `POINT_ABSENCE_WITHOUT_LEAVE`, `POINT_UNIFORM_VIOLATION`, `LATE_TOLERANCE_MINUTES`, `REQUIRE_CHECKOUT`, `MAX_ABSENCE_PERCENT_EXAM_BAN`.
- [ ] **Step 5: Chạy test quản trị học vụ**
  - Run: `pytest backend/tests/test_admin_academic.py -v`
  - Expected: PASS.

---

### Task 4: Phân hệ Điểm danh Kiosk AI (FaceID + Check-in/Check-out + Đồng phục)

**Files:**
- Modify: `backend/src/detect_ai/streamers/face_store.py`
- Create: `backend/src/detect_ai/services/kiosk_service.py`
- Create: `backend/src/detect_ai/api/routes_kiosk.py`
- Modify: `backend/src/detect_ai/main.py`
- Test: `backend/tests/test_kiosk.py`

**Interfaces:**
- Consumes: `verify_kiosk_api_key`, `face_store` index, AI models
- Produces:
  - `POST /api/v1/attendance/kiosk-record`:
    - Payload: `{ "room_name": str, "student_code": str, "has_uniform": bool, "timestamp": datetime }`
    - Tự động tìm `schedule_id` đang diễn ra tại phòng:
      `room_name = :room AND study_date = :today AND start_time - 30m <= :now <= end_time + 30m`.
    - Phân định Check-in vs Check-out:
      - Nếu chưa có bản ghi attendance cho `(schedule_id, student_id)`: Ghi nhận Check-in (`check_in_time = timestamp`, `has_uniform = has_uniform`).
      - Nếu đã có Check-in: Ghi nhận Check-out (`check_out_time = timestamp`).
  - Đồng bộ `face_store.py`: Nạp embeddings trực tiếp từ bảng `student_profiles` (`JOIN users u ON sp.user_id = u.id WHERE u.is_active = TRUE AND u.deleted_at IS NULL`).

- [ ] **Step 1: Viết test cho luồng ghi nhận Kiosk Check-in và Check-out**
  - Viết `backend/tests/test_kiosk.py` kiểm tra gọi Kiosk API:
    - Quét lần 1 (đầu giờ) -> Tạo record `check_in_time`.
    - Quét lần 2 (cuối giờ) -> Cập nhật `check_out_time`.
    - Quét ngoài giờ học của phòng -> Trả thông báo lỗi/không tìm thấy ca học.
- [ ] **Step 2: Nâng cấp `face_store.py`**
  - Đổi nguồn nạp vector từ bảng `student_profiles` (`student_profiles.face_embedding`), duy trì in-memory Faiss index để tốc độ tra cứu $< 10$ms.
- [ ] **Step 3: Cài đặt `kiosk_service.py` & `routes_kiosk.py`**
  - Tìm lịch học hiện tại theo `room_name` và thời gian thực.
  - Ghi nhận Check-in và Check-out an toàn, chống ghi đè lỗi.
- [ ] **Step 4: Chạy test Kiosk**
  - Run: `pytest backend/tests/test_kiosk.py -v`
  - Expected: PASS.

---

### Task 5: Luồng Đơn Nghỉ phép & Tích hợp Supabase Storage

**Files:**
- Create: `backend/src/detect_ai/services/storage_service.py`
- Create: `backend/src/detect_ai/api/routes_leave_requests.py`
- Modify: `backend/src/detect_ai/main.py`
- Test: `backend/tests/test_leave_workflow.py`

**Interfaces:**
- Consumes: Supabase Storage bucket `leave-proofs`, JWT Auth
- Produces:
  - Sinh viên: `POST /api/v1/student/leave-requests`:
    - Form-data: `schedule_id`, `reason`, `proof_file` (MIME validation, $\le 5$MB).
    - Lưu file vào bucket Supabase `leave-proofs`, lưu URL vào DB, `status = PENDING`.
  - Sinh viên: `GET /api/v1/student/leave-requests`: Xem danh sách đơn của mình và trạng thái duyệt.
  - Giảng viên: `GET /api/v1/teacher/leave-requests`: Xem các đơn của lớp mình phụ trách.
  - Giảng viên: `POST /api/v1/teacher/leave-requests/{id}/review`:
    - Enforce quyền: Giảng viên chỉ duyệt đơn của lớp mình dạy (`class.teacher_id == current_user.id`).
    - Body: `{ "status": "APPROVED" | "REJECTED", "feedback": str }`.
    - Nếu `APPROVED`: Cập nhật `attendance.status = 'EXCUSED'`.
    - **Cơ chế Hoàn điểm duyệt muộn (Late Approval Refund)**: Nếu ca học đã được Cron đánh giá trừ điểm trước đó (`is_evaluated = TRUE` và có bản ghi trừ điểm trong `point_ledger`):
      Tự động ghi bản ghi hoàn điểm vào `point_ledger` (`point_delta = +5`, `reason_code = 'LEAVE_REFUND'`) và tăng lại `users.total_point`.

- [ ] **Step 1: Viết test cho luồng nộp và duyệt đơn xin nghỉ phép**
  - Viết `backend/tests/test_leave_workflow.py` bao gồm:
    - Test upload file hợp lệ (jpg/png/pdf <= 5MB) và file không hợp lệ (exe/txt hoặc > 5MB bị từ chối 422).
    - Test Giảng viên duyệt đơn `APPROVED` -> trạng thái buổi học thành `EXCUSED`.
    - Test Giảng viên khác lớp cố tình duyệt đơn -> bị 403 Forbidden.
    - Test hoàn điểm nếu đơn được duyệt sau khi Cron 23h59 đã chạy trừ điểm.
- [ ] **Step 2: Cài đặt `storage_service.py`**
  - Tải file lên Supabase Storage bucket `leave-proofs` (fallback lưu local nếu chạy offline test).
- [ ] **Step 3: Cài đặt `routes_leave_requests.py`**
  - Endpoints nộp đơn cho Sinh viên và duyệt đơn cho Giảng viên.
- [ ] **Step 4: Chạy test luồng đơn phép**
  - Run: `pytest backend/tests/test_leave_workflow.py -v`
  - Expected: PASS.

---

### Task 6: Động cơ Đánh giá Tự động 23h59 (Nightly Evaluation Cron & Point Ledger)

**Files:**
- Create: `backend/src/detect_ai/services/evaluation_service.py`
- Create: `backend/src/detect_ai/api/routes_evaluation.py`
- Modify: `backend/src/detect_ai/main.py`
- Test: `backend/tests/test_evaluation_cron.py`

**Interfaces:**
- Consumes: APScheduler, `SystemSetting`, `Attendance`, `PointLedger`
- Produces:
  - Service: `run_nightly_evaluation(target_date: date)`:
    - **Lọc**: Tìm các schedules trong ngày có `is_evaluated = FALSE`.
    - Duyệt danh sách sinh viên đăng ký lớp (`class_students`):
      - Nếu `is_manual_override = TRUE`: Tôn trọng `status` và `note` do giáo viên chỉnh sửa.
      - Nếu có đơn `leave_requests.status = 'APPROVED'`: `status = 'EXCUSED'`, `point_delta = 0`.
      - Ngược lại, đối chiếu Check-in/out:
        - Check `REQUIRE_CHECKOUT` (true/false):
          - Đủ cả in & out, đúng giờ, có đồng phục -> `PRESENT`, cộng 2 điểm.
          - Chỉ có Check-in, thiếu Check-out -> `HALF_ABSENT`, trừ 2 điểm.
          - Đến muộn quá `LATE_TOLERANCE_MINUTES` -> `LATE`, trừ 1 điểm.
          - Không có dữ liệu quét -> `ABSENT`, trừ 5 điểm.
          - Vi phạm đồng phục (`has_uniform = FALSE`) -> Trừ thêm 2 điểm.
      - Ghi log sổ cái `point_ledger` (`reason_code = 'NIGHTLY_EVAL'`).
      - Đánh dấu `is_evaluated = TRUE`, `evaluated_at = NOW()`.
      - Cập nhật `users.total_point = MAX(0, total_point + point_delta)`.
  - Endpoint: `POST /api/v1/admin/evaluation/run-now` (cho phép Admin kích hoạt chạy bù thủ công).
  - Tích hợp APScheduler chạy tự động vào 23:59 mỗi ngày trong Lifespan.

- [ ] **Step 1: Viết test cho thuật toán đánh giá 23h59 và tính Idempotency**
  - Viết `backend/tests/test_evaluation_cron.py`:
    - Case đủ in/out -> PRESENT, +2 điểm.
    - Case thiếu out -> HALF_ABSENT, -2 điểm.
    - Case không quẹt -> ABSENT, -5 điểm.
    - Case giáo viên sửa tay -> giữ nguyên status của giáo viên.
    - Case chạy lại `run-now` lần 2 -> bỏ qua các bản ghi đã `is_evaluated=True`, không bị trừ điểm 2 lần.
- [ ] **Step 2: Cài đặt `evaluation_service.py`**
  - Đọc các giá trị config từ `system_settings`, thực thi thuật toán Idempotent theo quy chuẩn.
- [ ] **Step 3: Cài đặt router `routes_evaluation.py` và cấu hình APScheduler trong `main.py`**
- [ ] **Step 4: Chạy test đánh giá tự động**
  - Run: `pytest backend/tests/test_evaluation_cron.py -v`
  - Expected: PASS.

---

### Task 7: Nghiệp vụ Giảng viên & Xuất Báo cáo Cấm thi (Teacher Portal API & Exam-Ban Report)

**Files:**
- Create: `backend/src/detect_ai/services/report_service.py`
- Create: `backend/src/detect_ai/api/routes_teacher.py`
- Modify: `backend/src/detect_ai/main.py`
- Test: `backend/tests/test_teacher_and_reports.py`

**Interfaces:**
- Consumes: `require_role('TEACHER')`, `Class`, `Attendance`, `Schedule`
- Produces:
  - `GET /api/v1/teacher/classes`: Danh sách lớp giảng viên phụ trách.
  - `GET /api/v1/teacher/classes/{class_id}/live-attendance`: Sĩ số lớp theo thời gian thực (tổng sĩ số, đã check-in, chưa check-in, vi phạm đồng phục).
  - `PUT /api/v1/teacher/attendance/{attendance_id}/manual-override`:
    - Giảng viên sửa điểm danh thủ công: gán `status`, `note`, `is_manual_override = TRUE`, `updated_by = current_user.id`.
  - `GET /api/v1/teacher/classes/{class_id}/exam-ban-report`:
    - Tính toán theo 2 công thức:
      - Tỷ lệ cảnh báo lũy kế hiện tại: $(N_{vắng} + 0.5 \times N_{nửa\_buổi}) / N_{buổi\_đã\_diễn\_ra} \times 100\%$ (Cảnh báo nếu $\ge 15\%$).
      - Tỷ lệ cấm thi chính thức cả kỳ: $(N_{vắng} + 0.5 \times N_{nửa\_buổi}) / total\_sessions \times 100\%$ (Cấm thi nếu $\ge 20\%$).
  - `GET /api/v1/teacher/classes/{class_id}/export-exam-ban-excel`: Xuất file Excel (.xlsx) danh sách cấm thi của **từng môn** do giảng viên phụ trách.
  - `GET /api/v1/admin/reports/export-exam-ban-all-excel`: Xuất file Excel (.xlsx) danh sách cấm thi của **toàn trường** (Admin).

- [ ] **Step 1: Viết test cho nghiệp vụ Giảng viên và tính toán cấm thi (môn học & toàn trường)**
  - Viết `backend/tests/test_teacher_and_reports.py` kiểm tra live attendance, sửa điểm thủ công (ghi nhận cờ override), kiểm tra công thức tính tỷ lệ vắng và xuất file Excel theo từng lớp và toàn trường.
- [ ] **Step 2: Cài đặt `report_service.py`**
  - Hàm tính tỷ lệ vắng và hàm sinh file Excel sử dụng `openpyxl` hỗ trợ cả scope lớp học phần (GV) và scope toàn trường (Admin).
- [ ] **Step 3: Cài đặt `routes_teacher.py`**
  - Đầy đủ các endpoint cho Giảng viên.
- [ ] **Step 4: Chạy test nghiệp vụ Giảng viên**
  - Run: `pytest backend/tests/test_teacher_and_reports.py -v`
  - Expected: PASS.

---

### Task 8: Frontend - Shell Layout & Token System Chuẩn SaaS Quản lý (Linear / Stripe style)

**Files:**
- Create: `frontend/lib/auth-context.tsx`
- Create: `frontend/components/layout/sidebar.tsx`
- Create: `frontend/components/layout/topbar.tsx`
- Create: `frontend/components/layout/role-guard.tsx`
- Create: `frontend/app/login/page.tsx`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes: `/api/v1/auth/login`, `/api/v1/auth/me`
- Produces: Hệ thống layout chuẩn SaaS quản trị (Restrained Enterprise): Tông màu slate/zinc sạch sẽ, 1px border tinh tế, font số `tabular-nums`, không hiệu ứng màu mè hay gradient phát sáng AI; Sidebar + Topbar phân nhánh theo Role (Student, Teacher, Admin).

- [ ] **Step 1: Cập nhật thư viện frontend**
  - Cài đặt `lucide-react` để hỗ trợ icon đồng bộ cho CRM Dashboard.
- [ ] **Step 2: Cài đặt `auth-context.tsx` & `lib/api.ts`**
  - Lưu và đọc access token, cung cấp `useAuth()` hook chứa `{ user, role, login, logout, isAuthenticated }`.
- [ ] **Step 3: Xây dựng trang Đăng nhập `/login`**
  - Giao diện đăng nhập chuẩn, nhập mã người dùng (user_code) và mật khẩu, xử lý loading và hiển thị lỗi.
- [ ] **Step 4: Xây dựng Shell Dashboard (`sidebar.tsx`, `topbar.tsx`, `role-guard.tsx`)**
  - Sidebar hiển thị menu tùy theo quyền:
    - Sinh viên: Lịch học (TKB), Lịch sử điểm danh, Điểm rèn luyện, Đơn xin phép.
    - Giảng viên: Lớp học phụ trách, Điểm danh trực tiếp (Live), Duyệt đơn phép, Báo cáo cấm thi.
    - Quản trị viên: Quản lý người dùng, Quản lý lớp & TKB, Cấu hình tham số, Báo cáo toàn trường.
    - Kiosk Camera: Lối vào màn hình quét FaceID.

---

### Task 9: Frontend - Phân hệ Sinh viên (Student Portal)

**Files:**
- Create: `frontend/app/student/schedule/page.tsx`
- Create: `frontend/app/student/attendance/page.tsx`
- Create: `frontend/app/student/conduct-points/page.tsx`
- Create: `frontend/app/student/leave-requests/page.tsx`
- Create: `frontend/components/student/leave-request-modal.tsx`

**Interfaces:**
- Consumes: `/api/v1/student/*` APIs
- Produces:
  - Xem Thời khóa biểu cá nhân theo tuần/tháng.
  - Xem Lịch sử điểm danh theo từng môn học, trạng thái có mặt, muộn, nghỉ phép.
  - Xem Sổ cái điểm rèn luyện (`point_ledger`) và tổng điểm hiện tại kèm diễn giải chi tiết.
  - Form gửi đơn xin nghỉ phép trực tuyến kèm upload ảnh giấy khám bệnh (minh chứng) và xem danh sách đơn đã nộp.

- [ ] **Step 1: Xây dựng trang Thời khóa biểu (`/student/schedule`)**
  - Hiển thị danh sách các buổi học sắp diễn ra, phòng học, ca học, giảng viên phụ trách.
- [ ] **Step 2: Xây dựng trang Lịch sử Điểm danh (`/student/attendance`)**
  - Bảng thống kê lịch sử quét mã, giờ check-in, check-out, tình trạng đồng phục và trạng thái (Có mặt / Muộn / Có phép / Vắng).
- [ ] **Step 3: Xây dựng trang Sổ cái Điểm Rèn luyện (`/student/conduct-points`)**
  - KPI Card hiển thị tổng điểm hiện tại (trên thang 100), biểu đồ hoặc bảng biến động điểm (+2, -1, -5, +5 hoàn điểm) kèm ngày giờ và lý do chi tiết.
- [ ] **Step 4: Xây dựng trang Đơn xin nghỉ phép (`/student/leave-requests`)**
  - Danh sách đơn đã nộp kèm trạng thái `Chờ duyệt`, `Đã chấp nhận`, `Bị từ chối`.
  - Nút "+ Tạo đơn mới" mở modal: Chọn môn học -> Chọn buổi học -> Nhập lý do -> Tải lên ảnh giấy khám bệnh.

---

### Task 10: Frontend - Phân hệ Giảng viên (Teacher Portal)

**Files:**
- Create: `frontend/app/teacher/classes/page.tsx`
- Create: `frontend/app/teacher/classes/[id]/live/page.tsx`
- Create: `frontend/app/teacher/leave-reviews/page.tsx`
- Create: `frontend/app/teacher/reports/page.tsx`
- Create: `frontend/components/teacher/manual-override-modal.tsx`
- Create: `frontend/components/teacher/proof-preview-modal.tsx`

**Interfaces:**
- Consumes: `/api/v1/teacher/*` APIs
- Produces:
  - Quản lý danh sách lớp giảng dạy.
  - Giám sát Sĩ số thời gian thực (Live Attendance Room View): card sĩ số (Tổng số, Đã check-in, Vắng, Chưa có đồng phục), bảng danh sách sinh viên realtime.
  - Nút sửa điểm thủ công (Manual Override): đổi trạng thái điểm danh và ghi chú lý do.
  - Màn hình duyệt đơn xin nghỉ phép: xem ảnh giấy khám bệnh dạng modal phóng to, bấm Duyệt / Từ chối kèm phản hồi.
  - Xuất báo cáo cấm thi: hiển thị tỷ lệ vắng và nút tải file Excel (.xlsx).

- [ ] **Step 1: Xây dựng trang Danh sách lớp (`/teacher/classes`)**
  - Hiển thị danh sách lớp học phần phụ trách, tổng số sinh viên, số buổi đã học.
- [ ] **Step 2: Xây dựng trang Sĩ số thời gian thực (`/teacher/classes/[id]/live`)**
  - Giao diện Live Room: Tự động refresh hoặc qua polling kiểm tra sĩ số, lọc sinh viên chưa tới lớp, sinh viên vi phạm đồng phục.
  - Tích hợp modal sửa điểm thủ công cho từng sinh viên.
- [ ] **Step 3: Xây dựng trang Duyệt đơn nghỉ phép (`/teacher/leave-reviews`)**
  - Tab "Chờ duyệt" và "Lịch sử duyệt".
  - Xem chi tiết đơn, xem ảnh giấy khám bệnh (phóng to/thu nhỏ), form nhập feedback và nút Chấp nhận/Từ chối.
- [ ] **Step 4: Xây dựng trang Báo cáo Cấm thi (`/teacher/reports`)**
  - Bảng danh sách sinh viên có nguy cơ bị cấm thi ($\ge 15\%$) và danh sách chính thức bị cấm thi ($\ge 20\%$).
  - Nút "Xuất báo cáo Excel" tải trực tiếp file `.xlsx` về máy.

---

### Task 11: Frontend - Phân hệ Quản trị viên (Admin Portal)

**Files:**
- Create: `frontend/app/admin/users/page.tsx`
- Create: `frontend/app/admin/academic/page.tsx`
- Create: `frontend/app/admin/settings/page.tsx`
- Create: `frontend/app/admin/reports/page.tsx`
- Create: `frontend/components/admin/user-form-modal.tsx`
- Create: `frontend/components/admin/schedule-form-modal.tsx`

**Interfaces:**
- Consumes: `/api/v1/admin/*` APIs
- Produces:
  - Quản lý Sinh viên & Giảng viên (Thêm mới, upload ảnh chân dung trích xuất vector khuôn mặt, sửa thông tin, xóa mềm).
  - Quản lý Lớp học phần & Lịch học (Tạo lớp, thêm sinh viên vào lớp, tạo TKB chống trùng phòng).
  - Cấu hình Tham số Hệ thống (Điểm cộng/trừ, thời gian cho phép trễ, chế độ bắt buộc check-out).
  - Báo cáo Học vụ toàn trường & Nút kích hoạt chạy Cron 23h59 ngay ("Chạy tính điểm hôm nay").

- [ ] **Step 1: Xây dựng trang Quản lý Người dùng (`/admin/users`)**
  - Bảng dữ liệu người dùng (phân loại Sinh viên, Giảng viên), tìm kiếm theo tên hoặc mã.
  - Modal thêm người dùng: hỗ trợ tải ảnh chân dung và hiển thị trạng thái sinh vector FaceID.
- [ ] **Step 2: Xây dựng trang Quản lý Lớp & TKB (`/admin/academic`)**
  - Quản lý danh sách lớp, danh sách sinh viên trong lớp.
  - Quản lý Thời khóa biểu: Form xếp lịch có validate hiển thị cảnh báo nếu phòng học bị trùng lịch.
- [ ] **Step 3: Xây dựng trang Cấu hình Hệ thống (`/admin/settings`)**
  - Form cấu hình các tham số điểm thưởng/phạt, thời gian trễ, bật/tắt yêu cầu Check-out.
  - Nút "Kích hoạt Chạy tính điểm ngay (Run Now)" kèm thông báo kết quả.
- [ ] **Step 4: Xây dựng trang Báo cáo Tổng hợp (`/admin/reports`)**
  - Thống kê toàn trường về tỷ lệ chuyên cần và danh sách cấm thi theo từng khoa/lớp.

---

### Task 12: Màn hình Điểm danh Kiosk AI (FaceID & Quét Đồng phục)

**Files:**
- Create: `frontend/app/diem-danh/page.tsx`
- Create: `frontend/components/kiosk/camera-feed.tsx`
- Create: `frontend/components/kiosk/attendance-result-card.tsx`

**Interfaces:**
- Consumes: Camera WebRTC / WebSocket `/ws/attendance/webcam` hoặc `/api/v1/attendance/kiosk-record`
- Produces: Giao diện Kiosk toàn màn hình đặt tại cửa lớp học hoặc sảnh trường.
  - Khung hình camera trực tiếp với bounding box khuôn mặt và bounding box trang phục.
  - Thông báo hiển thị tức thì khi nhận diện thành công:
    - Họ tên, Mã SV, Lớp học phần.
    - Trạng thái Check-in hoặc Check-out.
    - Kết quả đồng phục: Hợp lệ (Áo đồng phục) hoặc Không hợp lệ.
    - Âm thanh beep phản hồi (Check-in thành công / Vi phạm).

- [ ] **Step 1: Xây dựng giao diện Kiosk toàn màn hình (`/diem-danh`)**
  - Thiết kế UI tối ưu cho màn hình Kiosk / Tablet: Đồng hồ số lớn, thông tin phòng học hiện tại, chuyển đổi chế độ Tự động / Check-in / Check-out.
- [ ] **Step 2: Tích hợp WebSocket luồng nhận diện AI**
  - Hiển thị bounding box màu xanh (đúng đồng phục, nhận diện thành công) hoặc màu đỏ/cam (chưa nhận diện hoặc vi phạm).
- [ ] **Step 3: Card hiển thị kết quả và thông báo âm thanh**
  - Hiện thẻ thông tin sinh viên vừa quét trong 3 giây rồi trở về trạng thái chờ.

---

### Task 13: Kiểm thử Tích hợp Toàn diện & Hướng dẫn Vận hành

**Files:**
- Create: `backend/tests/test_e2e_flow.py`
- Create: `docs/DATABASE_SETUP_GUIDE.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: Toàn bộ hệ thống Backend, Supabase và Frontend
- Produces: Bộ test E2E kiểm tra toàn bộ kịch bản nghiệp vụ; Tài liệu cấu hình Supabase và hướng dẫn chạy hệ thống.

- [ ] **Step 1: Viết test E2E cho kịch bản hoàn chỉnh (`test_e2e_flow.py`)**
  - Kịch bản 1: Sinh viên đi học đúng giờ, check-in, check-out, có đồng phục -> Cron 23h59 cộng 2 điểm.
  - Kịch bản 2: Sinh viên quên check-out -> Cron 23h59 đánh vắng nửa buổi, trừ 2 điểm.
  - Kịch bản 3: Sinh viên vắng nộp đơn kèm ảnh giấy khám bệnh -> Giảng viên duyệt -> Cập nhật nghỉ có phép, không trừ điểm.
  - Kịch bản 4: Giảng viên duyệt đơn muộn sau 23h59 -> Hệ thống hoàn điểm tự động.
  - Kịch bản 5: Sinh viên vắng quá 20% số buổi -> Xuất hiện trong danh sách cấm thi và file Excel.
- [ ] **Step 2: Chạy toàn bộ test suite backend**
  - Run: `pytest backend/tests -v`
  - Expected: ALL TESTS PASS.
- [ ] **Step 3: Soạn thảo tài liệu thiết lập CSDL Supabase (`docs/DATABASE_SETUP_GUIDE.md`)**
  - Hướng dẫn tạo Project trên Supabase.
  - Hướng dẫn chạy DDL script `01_schema.sql` và `02_seed.sql`.
  - Hướng dẫn tạo 2 Storage bucket `leave-proofs` và `avatars` với quyền public/signed URL.
  - Hướng dẫn cấu hình biến môi trường trong file `.env`.
- [ ] **Step 4: Cập nhật tài liệu vận hành `README.md`**
  - Cập nhật hướng dẫn khởi chạy cả Backend, AI Kiosk và Frontend Next.js.

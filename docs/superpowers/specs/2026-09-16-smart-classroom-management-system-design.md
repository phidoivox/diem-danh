# ĐẶC TẢ THIẾT KẾ KIẾN TRÚC HỆ THỐNG (PHIÊN BẢN 2.0 - ĐÃ CẬP NHẬT)
## HỆ THỐNG QUẢN LÝ LỚP HỌC THÔNG MINH (SMART CLASSROOM MANAGEMENT SYSTEM)
**Đề tài:** Tích hợp Điểm danh AI, Kiểm soát Tác phong và Đánh giá Rèn luyện  
**Nền tảng CSDL:** Supabase (PostgreSQL + Supabase Storage)  
**Công nghệ:** FastAPI (Backend) + Next.js / Tailwind CSS (Frontend) + AI Engine hiện có  
**Ngày cập nhật:** 16-09-2026  
**Trạng thái:** Bản thiết kế kiến trúc chuẩn phê duyệt (Approved Architectural Spec)

---

## 1. TỔNG QUAN & PHẠM VI HỆ THỐNG

### 1.1. Bối cảnh & Mục tiêu
Hệ thống giải quyết triệt để các bất cập trong quy trình quản lý học vụ và chuyên cần truyền thống:
* Loại bỏ việc gọi tên thủ công, chống gian lận điểm danh hộ.
* Số hóa $100\%$ quy trình nộp và phê duyệt đơn xin nghỉ phép trực tuyến có đính kèm ảnh minh chứng.
* Tự động hóa đánh giá chuyên cần & điểm rèn luyện tác phong học vụ vào lúc 23h59 hàng ngày.
* Phát hiện nguy cơ cấm thi sớm, gửi cảnh báo chủ động và xuất báo cáo cấm thi chuẩn cho phòng Đào tạo.
* **Làm rõ bản chất điểm số**: `total_point` trong hệ thống là **"Điểm Chuyên cần & Tác phong Học vụ" (Attendance & Discipline Score)**, là thước đo điện tử minh bạch cung cấp số liệu thành phần cho Phòng Công tác Sinh viên (CTSV) tổng hợp điểm rèn luyện chung toàn trường.

### 1.2. Nguyên tắc phân tách Kiến trúc
* **Core Academic Engine**: Chịu trách nhiệm toàn bộ logic người dùng, lớp học, thời khóa biểu, đơn từ, sổ cái điểm và báo cáo.
* **AI Kiosk Service (Module độc lập)**: Chịu trách nhiệm camera, nhận diện khuôn mặt và trang phục. Giao tiếp với Core Backend thông qua API riêng biệt xác thực bằng `API Key`.

---

## 2. SƠ ĐỒ KIẾN TRÚC TỔNG THỂ & LUỒNG DỮ LIỆU

```
+---------------------------------------------------------------------------------------------------+
|                                     TẦNG GIAO DIỆN (CLIENT TIER)                                   |
|                                                                                                   |
|  [ Student Portal ]               [ Teacher Portal ]                  [ Admin Portal ]            |
|  - TKB cá nhân & Lịch sử          - Danh sách lớp phụ trách           - Quản trị Users & RBAC     |
|  - Tra cứu Sổ cái điểm            - Sĩ số live & Sửa điểm thủ công   - Quản lý Lớp & TKB         |
|  - Nộp đơn nghỉ + upload minh chứng- Duyệt đơn nghỉ kèm minh chứng     - Cấu hình System Settings  |
|                                                                       - Báo cáo & Xuất cấm thi    |
|                                                                                                   |
|  [ Kiosk Điểm Danh (Edge / Web Client) ]                                                          |
|  - Webcam / IP Camera -> Gọi API: POST /api/v1/attendance/kiosk-record                            |
|  - Xác thực riêng biệt qua Header: X-Kiosk-Api-Key                                                |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  | REST API (JSON) + JWT Bearer Auth / Kiosk API Key
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                     TẦNG MÁY CHỦ (FASTAPI BACKEND)                                |
|                                                                                                   |
|  [1. Auth & RBAC Service]                                                                         |
|  - Xác thực JWT, enforce quyền sở hữu lớp ở tầng service (GV chỉ thao tác trên lớp mình dạy)     |
|                                                                                                   |
|  [2. Academic & Scheduling Service]                                                               |
|  - Quản lý Users (Soft-delete), Classes, Class_Students, Schedules (Kiểm tra chống trùng phòng)   |
|                                                                                                   |
|  [3. Leave Request Workflow Service]                                                              |
|  - Nộp đơn online (Validate file <= 5MB, JPG/PNG/PDF), lưu URL Supabase Storage                  |
|  - Duyệt đơn (Approve/Reject) -> Tự động đồng bộ Attendance & Hoàn điểm nếu duyệt muộn            |
|                                                                                                   |
|  [4. Nightly Evaluation Engine (Cron 23h59 & Run-Now) - ĐẢM BẢO IDEMPOTENCY]                      |
|  - APScheduler / Worker: Chỉ xử lý các buổi học chưa evaluate (is_evaluated = FALSE)              |
|  - Tôn trọng cờ sửa tay của Giảng viên (is_manual_override = TRUE -> không ghi đè status)          |
|  - Ghi vết mọi biến động điểm vào bảng Sổ cái Point_Ledger                                        |
|                                                                                                   |
|  [5. Notification & Email Service]                                                                |
|  - BackgroundTasks gửi email cảnh báo nguy cơ cấm thi và thông báo kết quả duyệt đơn              |
|                                                                                                   |
|  [6. AI Stream Engine - KẾ THỪA NGUYÊN VẸN CODE HIỆN TẠI]                                         |
|  - Pipeline, Tracker, InsightFace + Liveness, Faiss Index (In-memory cache nạp từ CSDL)           |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  | Async SQLAlchemy (asyncpg) / Supabase Client
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                 TẦNG CƠ SỞ DỮ LIỆU (SUPABASE POSTGRESQL)                          |
|                                                                                                   |
|  [ 9 Bảng chuẩn 3NF với Soft-Delete & Point Ledger ]:                                             |
|  - Roles, Users (Soft-delete), Classes, Class_Students, Schedules (Chống trùng),                 |
|    Attendance (Enum status, cờ override/evaluated), Leave_Requests (Enum status),                 |
|    Point_Ledger (Sổ cái điểm), System_Settings                                                    |
|                                                                                                   |
|  [ Supabase Storage S3-Compatible Buckets ]:                                                      |
|  - Bucket 'leave-proofs': Ảnh/PDF minh chứng đơn nghỉ phép (Chặn mime type, giới hạn 5MB)         |
|  - Bucket 'avatars': Ảnh chân dung sinh viên, giảng viên                                          |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. THIẾT KẾ CƠ SỞ DỮ LIỆU CHI TIẾT (SUPABASE POSTGRESQL)

### 3.1. Định nghĩa Kiểu Liệt Kê (PostgreSQL Enums)
Để loại bỏ hoàn toàn lỗi chính tả, các trạng thái được chuẩn hóa bằng Enum:
```sql
CREATE TYPE attendance_status AS ENUM ('PRESENT', 'LATE', 'HALF_ABSENT', 'ABSENT', 'EXCUSED');
CREATE TYPE leave_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
CREATE TYPE user_role AS ENUM ('ADMIN', 'TEACHER', 'STUDENT');
```

---

### 3.2. Bảng `roles` (Vai trò)
| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `id` | `INT` | `PRIMARY KEY` | 1: Admin, 2: Giảng viên, 3: Sinh viên |
| `role_name` | `VARCHAR(50)` | `UNIQUE, NOT NULL` | `ADMIN`, `TEACHER`, `STUDENT` |

---

### 3.3. Bảng `users` (Người dùng - Hỗ trợ Soft Delete & Bảo mật Sinh trắc)
| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `id` | `SERIAL` | `PRIMARY KEY` | Khóa chính tự tăng |
| `user_code` | `VARCHAR(20)` | `UNIQUE, NOT NULL` | Mã SV hoặc Mã GV (VD: `SV2023001`, `GV01`) |
| `full_name` | `VARCHAR(100)` | `NOT NULL` | Họ và tên |
| `email` | `VARCHAR(100)` | `UNIQUE, NOT NULL` | Email nhận cảnh báo học vụ |
| `password_hash` | `VARCHAR(255)` | `NOT NULL` | Mật khẩu mã hóa Bcrypt |
| `role_id` | `INT` | `FK -> roles(id)` | Vai trò |
| `face_embedding` | `TEXT` | `NULL` | Vector 512 chiều (Source of truth, bảo mật theo NĐ 13/2023) |
| `avatar_url` | `VARCHAR(500)` | `NULL` | URL ảnh chân dung |
| `total_point` | `INT` | `DEFAULT 100` | Điểm chuyên cần hiện tại (tính từ `point_ledger`) |
| `is_active` | `BOOLEAN` | `DEFAULT TRUE` | Trạng thái tài khoản |
| `deleted_at` | `TIMESTAMPTZ` | `NULL` | Đánh dấu thời điểm xóa mềm (Soft delete) |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | Ngày tạo |

---

### 3.4. Bảng `classes` (Lớp học phần)
| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `id` | `SERIAL` | `PRIMARY KEY` | Khóa chính |
| `class_code` | `VARCHAR(50)` | `UNIQUE, NOT NULL` | Mã lớp học phần (VD: `COMP101.1`) |
| `course_name` | `VARCHAR(100)` | `NOT NULL` | Tên môn học |
| `teacher_id` | `INT` | `FK -> users(id) ON DELETE RESTRICT` | Giảng viên phụ trách |
| `semester` | `VARCHAR(20)` | `NOT NULL` | Học kỳ (VD: `HK1_2026`) |
| `total_sessions` | `INT` | `DEFAULT 15` | Tổng số buổi học cả kỳ của môn |

---

### 3.5. Bảng `class_students` (Danh sách sinh viên trong lớp)
| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `class_id` | `INT` | `FK -> classes(id) ON DELETE CASCADE` | Lớp học phần |
| `student_id` | `INT` | `FK -> users(id) ON DELETE RESTRICT` | Sinh viên |
| *(Composite PK)* | | `PRIMARY KEY (class_id, student_id)` | Mỗi sinh viên chỉ nằm trong lớp 1 lần |

---

### 3.6. Bảng `schedules` (Thời khóa biểu từng buổi học - Chống trùng phòng)
| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `id` | `SERIAL` | `PRIMARY KEY` | Khóa chính |
| `class_id` | `INT` | `FK -> classes(id) ON DELETE CASCADE` | Lớp học phần |
| `room_name` | `VARCHAR(50)` | `NOT NULL` | Phòng học (VD: `A101`, `Lab 302`) |
| `study_date` | `DATE` | `NOT NULL` | Ngày diễn ra buổi học |
| `start_time` | `TIME` | `NOT NULL` | Giờ bắt đầu |
| `end_time` | `TIME` | `NOT NULL` | Giờ kết thúc |
| `session_order` | `INT` | `NOT NULL` | Buổi thứ mấy (1..15) |

* **Ràng buộc chống trùng phòng (Room Conflict Constraint)**:
  * Application-level check & DB Index: `CHECK start_time < end_time` và không được có 2 bản ghi cùng `room_name`, cùng `study_date` mà thời gian chồng lấn.

---

### 3.7. Bảng `attendance` (Lịch sử Điểm danh & Chuyên cần)
| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `id` | `SERIAL` | `PRIMARY KEY` | Khóa chính |
| `schedule_id` | `INT` | `FK -> schedules(id) ON DELETE CASCADE` | Buổi học |
| `student_id` | `INT` | `FK -> users(id) ON DELETE RESTRICT` | Sinh viên |
| `check_in_time` | `TIMESTAMPTZ` | `NULL` | Thời điểm check-in |
| `check_out_time` | `TIMESTAMPTZ`| `NULL` | Thời điểm check-out |
| `has_uniform` | `BOOLEAN` | `DEFAULT TRUE` | Trạng thái đồng phục |
| `status` | `attendance_status` | `DEFAULT 'ABSENT'` | `PRESENT`, `LATE`, `HALF_ABSENT`, `ABSENT`, `EXCUSED` |
| `is_manual_override`| `BOOLEAN` | `DEFAULT FALSE` | Đánh dấu Giảng viên đã can thiệp thủ công |
| `is_evaluated` | `BOOLEAN` | `DEFAULT FALSE` | Đánh dấu đã chạy tính điểm (Idempotency) |
| `evaluated_at` | `TIMESTAMPTZ` | `NULL` | Thời điểm chạy tính điểm rèn luyện |
| `note` | `VARCHAR(255)` | `NULL` | Lý do sửa thủ công |
| `updated_by` | `INT` | `FK -> users(id) NULL` | Giảng viên sửa điểm |
| `UNIQUE (schedule_id, student_id)` | | | 1 bản ghi duy nhất cho mỗi SV/buổi |

---

### 3.8. Bảng `leave_requests` (Đơn xin nghỉ phép trực tuyến)
| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `id` | `SERIAL` | `PRIMARY KEY` | Khóa chính |
| `schedule_id` | `INT` | `FK -> schedules(id) ON DELETE CASCADE` | Buổi học xin nghỉ |
| `student_id` | `INT` | `FK -> users(id) ON DELETE RESTRICT` | Sinh viên nộp đơn |
| `reason` | `TEXT` | `NOT NULL` | Lý do nghỉ |
| `proof_image` | `VARCHAR(500)` | `NULL` | URL file minh chứng (giới hạn $\le 5$MB, JPG/PNG/PDF) |
| `status` | `leave_status` | `DEFAULT 'PENDING'` | `PENDING`, `APPROVED`, `REJECTED` |
| `teacher_feedback` | `VARCHAR(255)` | `NULL` | Phản hồi của Giảng viên khi duyệt |
| `reviewed_by` | `INT` | `FK -> users(id) NULL` | Giảng viên duyệt đơn |
| `reviewed_at` | `TIMESTAMPTZ` | `NULL` | Thời điểm duyệt đơn |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | Ngày nộp |

---

### 3.9. Bảng MỚI: `point_ledger` (Sổ cái biến động điểm chuyên cần)
Đảm bảo tính minh bạch tuyệt đối và giải quyết khiếu nại của sinh viên:
| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `id` | `SERIAL` | `PRIMARY KEY` | Khóa chính |
| `student_id` | `INT` | `FK -> users(id) ON DELETE RESTRICT` | Sinh viên |
| `schedule_id` | `INT` | `FK -> schedules(id) ON DELETE SET NULL` | Buổi học phát sinh điểm |
| `point_delta` | `INT` | `NOT NULL` | Biến động điểm (VD: `+2`, `-1`, `-2`, `-5`) |
| `reason_code` | `VARCHAR(50)` | `NOT NULL` | Mã lý do (VD: `NIGHTLY_EVAL`, `MANUAL_OVERRIDE`, `LEAVE_REFUND`) |
| `description` | `VARCHAR(255)` | `NULL` | Diễn giải chi tiết (VD: "Đi học đúng giờ, đủ đồng phục") |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | Thời điểm ghi sổ |

---

### 3.10. Bảng `system_settings` (Cấu hình tham số hệ thống)
* `LATE_TOLERANCE_MINUTES` = `15` (Số phút cho phép đi muộn)
* `REQUIRE_CHECKOUT` = `false` (Nếu true: bắt buộc cả check-in và check-out mới tính đủ buổi. Mặc định false nếu trường chỉ lắp 1 camera cửa vào).
* `POINT_FULL_ATTENDANCE` = `2` (Cộng 2 điểm nếu đủ buổi, đúng giờ, có đồng phục)
* `POINT_LATE` = `-1` (Trừ 1 điểm nếu đi muộn)
* `POINT_HALF_ABSENCE` = `-2` (Trừ 2 điểm nếu vắng nửa buổi)
* `POINT_ABSENCE_WITHOUT_LEAVE` = `-5` (Trừ 5 điểm nếu vắng không phép)
* `POINT_UNIFORM_VIOLATION` = `-2` (Trừ 2 điểm nếu vi phạm tác phong)
* `MAX_ABSENCE_PERCENT_EXAM_BAN` = `20` (Ngưỡng % vắng tính trên cả kỳ để cấm thi)
* `WARNING_ABSENCE_PERCENT` = `15` (Ngưỡng cảnh báo học vụ sớm)

---

## 4. ĐẶC TẢ CHI TIẾT CÁC LUỒNG NGHIỆP VỤ & THUẬT TOÁN

### 4.1. Quy tắc Ưu tiên & Đảm bảo Idempotency của Cron 23h59
1. **Lọc dữ liệu**: Chỉ lấy các buổi học trong ngày có `is_evaluated = FALSE`.
2. **Ưu tiên Giáo viên sửa tay**:
   * Nếu `attendance.is_manual_override == TRUE`: Giữ nguyên `status` giáo viên đã chọn, không để cron tự suy diễn lại.
3. **Xử lý điểm danh tự động**:
   * Nếu có đơn nghỉ `leave_requests.status == 'APPROVED'`: `status = 'EXCUSED'`, `point_delta = 0`.
   * Nếu không có đơn phép:
     * Kiểm tra cờ `REQUIRE_CHECKOUT`:
       * Nếu `REQUIRE_CHECKOUT == false`: Có `check_in_time` $\rightarrow$ `status = 'PRESENT'` (hoặc `LATE` nếu quá `LATE_TOLERANCE_MINUTES`).
       * Nếu `REQUIRE_CHECKOUT == true`: Cần cả in và out; thiếu 1 trong 2 $\rightarrow$ `status = 'HALF_ABSENT'`.
     * Không có lượt quét nào $\rightarrow$ `status = 'ABSENT'`.
4. **Ghi sổ cái & Cập nhật**:
   * Ghi bản ghi vào `point_ledger` kèm `reason_code = 'NIGHTLY_EVAL'`.
   * Đánh dấu `attendance.is_evaluated = TRUE` và `evaluated_at = NOW()`.
   * Cập nhật `users.total_point = MAX(0, total_point + point_delta)`.
   * *Nếu chạy lại lệnh (`run-now`), hệ thống bỏ qua các buổi đã `is_evaluated = TRUE`, triệt tiêu hoàn toàn rủi ro cộng/trừ điểm trùng lặp.*

---

### 4.2. Xử lý Đơn nghỉ phép duyệt muộn (Late Approval & Refund Logic)
* **Kịch bản**: Sinh viên ốm nộp đơn hôm thứ Hai, Cron 23h59 thứ Hai đã trừ 5 điểm `ABSENT`. Đến thứ Tư Giảng viên mới mở portal và bấm Duyệt (`APPROVED`).
* **Thuật toán xử lý**:
  1. Cập nhật `leave_requests.status = 'APPROVED'`.
  2. Cập nhật `attendance.status = 'EXCUSED'`.
  3. Kiểm tra nếu buổi học đó đã bị Cron trừ điểm trước đó:
     * Ghi 1 bản ghi hoàn điểm vào `point_ledger`: `point_delta = +5`, `reason_code = 'LEAVE_REFUND'`, `description = 'Hoàn điểm do đơn phép được duyệt bổ sung'`.
     * Tăng lại `users.total_point = total_point + 5`.

---

### 4.3. Phân định Hai Công thức Tỷ lệ Vắng & Cảnh báo Cấm thi
Để loại bỏ hiện tượng pha loãng mẫu số ngay từ đầu kỳ:

1. **Tỷ lệ vắng lũy kế hiện tại (Dùng để Cảnh báo sớm trên Dashboard & Gửi Email)**:
   $$\text{Tỷ lệ vắng lũy kế (\%)} = \frac{N_{\text{vắng}} + (N_{\text{vắng nửa buổi}} \times 0.5)}{N_{\text{số buổi đã diễn ra đến nay}}} \times 100\%$$
   * Nếu tỷ lệ này $\ge 15\%$: Gửi email cảnh báo sinh viên và hiện cảnh báo màu vàng trên Portal.

2. **Tỷ lệ vắng chính thức cả học kỳ (Dùng để Chốt danh sách CẤM THI)**:
   $$\text{Tỷ lệ vắng cả kỳ (\%)} = \frac{N_{\text{vắng}} + (N_{\text{vắng nửa buổi}} \times 0.5)}{\text{Classes.total\_sessions}} \times 100\%$$
   * Khi tỷ lệ này $\ge 20\%$ (đạt ngưỡng quy chế trường): Hệ thống tự động gắn nhãn cấm thi đối với môn học đó và đưa vào báo cáo xuất Excel.

---

## 5. ĐẶC TẢ API & BẢO MẬT (API CONTRACT & SECURITY)

### 5.1. Xác thực Kiosk riêng biệt (Kiosk Service Authentication)
* `POST /api/v1/attendance/kiosk-record`:
  * **Header bắt buộc**: `X-Kiosk-Api-Key: <KIOSK_SECRET_KEY>`.
  * **Payload**: `{ "room_name": "A101", "student_code": "SV2023001", "has_uniform": true, "timestamp": "2026-09-16T07:45:00Z" }`.
  * Backend tự tìm `schedule_id` đang diễn ra tại `room_name` và ghi nhận check-in/out.

### 5.2. Enforce Phân quyền ở tầng Service (Service-Level RBAC)
* Giảng viên thao tác endpoint `/api/v1/teacher/classes/{class_id}/*` hoặc `/leave-requests/{id}/review`:
  * FastAPI Dependency kiểm tra bắt buộc: `class.teacher_id == current_user.id`. Nếu không trùng, trả về HTTP 403 Forbidden ngay lập tức.

### 5.3. Bảo mật Dữ liệu Sinh trắc học (Nghị định 13/2023/NĐ-CP)
* Cột `face_embedding` trong CSDL được bảo vệ. Tất cả các endpoint trả về thông tin người dùng (`UserResponseDTO`) đều **loại bỏ (exclude)** trường `face_embedding`.
* Chỉ service nội bộ xử lý AI mới có quyền đọc cột này để nạp vào Faiss Index.

### 5.4. Ràng buộc Upload Minh chứng Nghỉ phép
* Endpoint upload kiểm tra:
  * MIME types cho phép: `image/jpeg`, `image/png`, `application/pdf`.
  * Dung lượng tối đa: $\le 5\text{MB}$. File được lưu vào Supabase Storage bucket `leave-proofs`.

---

## 6. LỘ TRÌNH TRIỂN KHAI THEO GIAI ĐOẠN (ROADMAP)

| Giai đoạn | Mục tiêu | Kết quả bàn giao |
| :--- | :--- | :--- |
| **Pha 1: CSDL Supabase & Core Models** | Tạo 9 bảng, Enums, quan hệ, soft-delete, indexes chống trùng lịch phòng học. Cấu hình Supabase Storage. | DDL script chạy trên Supabase, SQLAlchemy models sẵn sàng. |
| **Pha 2: Quản trị & Xác thực RBAC** | Viết API JWT Auth, User CRUD (Soft-delete), Classes & Schedules CRUD (chống trùng phòng), Kiosk API Key. | Swagger `/docs` kiểm thử thành công các phân hệ quản lý. |
| **Pha 3: Luồng Đơn Phép & Engine 23h59** | Nộp/duyệt đơn nghỉ phép, Late approval refund, Nightly Evaluation đảm bảo Idempotency, ghi sổ cái Point_Ledger, tính tỷ lệ vắng 2 giai đoạn, xuất file Excel cấm thi. | Logic học vụ chạy hoàn chỉnh, pass toàn bộ unit test. |
| **Pha 4: 3 Phân hệ Portal (Next.js)** | Xây dựng Student Portal, Teacher Portal, Admin Portal với Tailwind CSS. Tích hợp sổ cái điểm và xem ảnh minh chứng. | Giao diện web hoàn chỉnh, thẩm mỹ, mượt mà. |
| **Pha 5: Tích hợp Module Kiosk AI** | Kết nối module AI webcam/RTSP hiện có với Kiosk endpoint qua API Key. | Toàn hệ thống hoàn thành $100\%$ theo báo cáo. |

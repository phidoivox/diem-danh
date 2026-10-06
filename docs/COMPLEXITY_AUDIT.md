# Phân tích Độ phức tạp & Cơ hội Đơn giản hoá — detect-ai

> **Phạm vi:** toàn bộ repo — `backend/src` **4.190 dòng**, `backend/tests` **4.398 dòng**,
> `frontend` **10.847 dòng** (app + components + lib). Tổng **~19.400 dòng**.
> **Phương pháp:** đọc trực tiếp từng file nguồn + đếm bằng grep; mọi kết luận đều kèm `file:dòng` để kiểm chứng.
> **Nguyên tắc:** chỉ nêu chỗ **lặp lại**, **chết**, **tự viết thứ thư viện đã làm tốt hơn**, hoặc **sai/rủi ro thật** —
> không đề xuất đổi công nghệ chỉ vì sở thích.
>
> **Quan hệ với tài liệu cũ:** `docs/CODE_SIMPLIFICATION_REVIEW.md` (commit `5f89916`) vẫn đúng phần lớn.
> Tài liệu này **thay thế** nó: xác minh lại từng mục trên mã nguồn hiện tại, bổ sung các phát hiện mới
> (§2), và cập nhật mục đã sửa (`core/supabase.py` nay dùng `storage3` — commit `26cc8e7`).

---

## 0. Trạng thái triển khai (cập nhật sau khi sửa)

**Đã sửa xong toàn bộ §1.2 (B1–B12) trừ B11**, cộng thêm phát hiện "double-guard `require_role`":

| Mã | Nội dung | Cách sửa |
|---|---|---|
| B1, B2 | `ai/tracker.py` thiếu `import supervision`; `ByteTrack` deprecated | Thêm import; ghim `supervision>=0.25,<0.31` trong `pyproject.toml` |
| B3 | Ngưỡng cấm thi hardcode 15/20 | Thêm `services/settings_repo.py`; `report_service` đọc từ `system_settings` (đọc 1 lần cho cả trường) |
| B4 | Khoá Kiosk hardcode + so sánh không hằng thời gian | Chỉ nhận `S.kiosk_api_key` + `secrets.compare_digest` |
| B5 | 2 thread RTSP chạy ngay lúc import | `RtspWorker._ensure_started()` — chỉ khởi động khi thực sự `open()`; hoãn nạp model |
| B6 | Không mount `/static` | Mount `/static/storage` (chỉ thư mục storage) + helper `mediaUrl()` ở frontend |
| B7 | Hai sổ đăng ký khuôn mặt | Xoá lớp legacy — nay chỉ còn `student_profiles.face_embedding` |
| B8 | `except (JWTError, Exception)` nuốt mọi lỗi | Chỉ bắt `JWTError`; bỏ 3 `getattr(S, ...)` thừa |
| B9 | Không có `app.add_exception_handler` | Thêm handler `IntegrityError` → 409 |
| B10 | ENUM native (SQL) vs `VARCHAR` (ORM) | Cả hai về `VARCHAR + CHECK`; `create_constraint=True` trong model |
| B11 | Drift schema, vá tay `ALTER TABLE` | **Chưa xử lý** — xem §5. Đã thêm `sql/03_migrate_existing_db.sql` cho Supabase |
| B12 | Đơn nghỉ phép không có ràng buộc chống trùng | Partial unique index `uq_leave_requests_active` (model + SQL + migration) |
| — | Double-guard `require_role` (2 query DB/request) | Singleton `require_admin` / `require_teacher` / `require_student` |

**Ngoài ra đã xoá lớp legacy** (~1.100 dòng, theo xác nhận của chủ dự án): `routes_students`,
`routes_attendance`, `routes_camera`, `api/schemas.py`, `models/student.py`,
`models/attendance.py`, `models/uniform_rule.py`, `streamers/rtsp_worker.py`,
`streamers/save_queue.py` và 3 trang `/attendance`, `/students`, `/reports`.

> ⚠️ **Thay đổi hành vi:** log ảnh snapshot lúc điểm danh không còn được ghi (trước đây
> `save_queue` ghi vào `legacy_attendance` và `data/snapshots/`); chỉ trang `/attendance` đã xoá
> tiêu thụ dữ liệu này. Endpoint hở giảm từ 12/45 xuống còn 4/36 — cả 4 đều là chủ ý
> (`login`, `kiosk-record`, `health`, `/metrics`).

**Kiểm chứng:** `pytest tests -q` → **85 passed**; `tsc --noEmit` → exit 0.


---

## 1. Tóm tắt điều hành

**Tổng tiềm năng giảm: ~3.500–4.000 dòng (~18–20%) mà không mất tính năng nào**, cộng với 10 lỗi thật
và một loạt khoảng trống về khả năng truy cập (a11y) không thể đo bằng số dòng.

### 1.1 Việc đáng làm nhất (xếp theo tỉ lệ lợi ích / rủi ro)

| # | Vấn đề | Vị trí | Cách đơn giản hơn | Giảm | Rủi ro |
|---|---|---|---|---|---|
| 1 | **13 trang tự viết máy trạng thái loading/error** (35 `useEffect`, 39 `catch`, 29 lần tự gọi lại `load()`) | `student/attendance:29-44` lặp ở 12 file khác | **SWR** hoặc **TanStack Query** — `useQuery`/`mutate` tự lo cache, loading, error, refetch | ~170 | Thấp |
| 2 | **8 modal tự viết `fixed inset-0`: 0 portal, 0 Escape, 0 focus-trap, 0 `role="dialog"`** | `leave-request-modal.tsx:83`, `user-form-modal.tsx:161`, `schedule-form-modal.tsx:98`, `face-enroll-modal.tsx:110`, `manual-override-modal.tsx:123`, `proof-preview-modal.tsx:49`, `academic/page.tsx:584,704` | **Radix Dialog** (hoặc Headless UI) + 1 `<Modal>` dùng chung → portal + Esc + focus-trap + aria miễn phí | ~240 | Trung bình |
| 3 | **12/13 bảng viết tay** trong khi `@tanstack/react-table` đã cài mà chỉ dùng ở 1 trang chết; 12 dòng `colSpan` loading/empty, 12 khối loading, 13 empty-state | `admin/users:242`, `admin/academic:361,507,763`, `live:436`… | `<DataTable>` + `useReactTable` | ~230 + 150 | Trung bình |
| 4 | **`lib/api.ts` 767 dòng / 83 export viết tay**, khối parse lỗi copy **4 lần** | `api.ts:83-95`, `:110-119`, `:752-761`, `:842-851` | Sinh type/client từ `/openapi.json` (**openapi-typescript** / **orval**) + 1 hàm `apiFetch` | **767 → ~180** | Trung bình |
| 5 | **174 dòng gán field DTO bằng tay** ở 24 chỗ; **16 model khai `from_attributes=True` nhưng `model_validate` xuất hiện 0 lần** trong toàn backend | `routes_admin_academic.py:142,195,267` (`ClassResponse` viết 3 lần), `routes_student_portal.py:101,143,191`, `routes_teacher.py:122,226,242,256` | `Model.model_validate(obj)` + `@computed_field` cho field dẫn xuất | ~100 | Thấp–TB |
| 6 | **9 form dùng 44 `useState` field**; `react-hook-form` đã cài mà chỉ dùng ở 1 form chết | `user-form-modal.tsx:22-36` + `:99-158`, `admin/settings:29-38`, `schedule-form-modal:22-27` | **react-hook-form** + **zod** (đọc lại docs Next 16: Server Action + `useActionState`) | ~250 | Thấp–TB |
| 7 | **9 file test tự dựng lại engine + PRAGMA**; 8 file tự dựng ASGI client; helper auth lặp 8 file | `test_auth.py:23`, `test_e2e_flow.py:76`, … (**không có `conftest.py`**) | Gom vào `backend/tests/conftest.py` + factory | ~290 | Thấp |
| 8 | **Excel style tay ~135 dòng**: `PatternFill/Font/Border`, merge cứng `"A1:I1"`, tự đo `max_len` | `report_service.py:165-302` | `pandas.DataFrame.to_excel(engine="xlsxwriter")` + `add_table()/set_column()`, hoặc `NamedStyle` | ~110 | Thấp |
| 9 | **5 chỗ đọc `system_settings` theo 3 kiểu khác nhau** + **ngưỡng cấm thi hardcode** | `report_service.py:104-105` (hardcode `15.0/20.0`) vs `evaluation_service.py:32-57`, `kiosk_service.py:109-111` | 1 `settings_repo.get_int/get_bool` có cache → **đồng thời sửa bug** | ~60 | Thấp |
| 10 | **8 bản format ngày tay** + 4 lần `toISOString().split("T")[0]`; **9 map status→màu** + 24 badge span trùng | `student/leave-requests:77-90`, `student/attendance:115-152`… | `lib/format.ts` (date-fns / `Intl`) + `lib/status.ts` + `<StatusBadge>` | ~260 | Thấp |

### 1.2 Bug & rủi ro thật (không chỉ là chuyện style)

| # | Vấn đề | Vị trí | Hệ quả |
|---|---|---|---|
| B1 | `tracker.py` dùng `sv.Detections` **nhưng không import `sv`** | `ai/tracker.py:8` | Chỉ chạy được nhờ `from __future__ import annotations`. Gọi `typing.get_type_hints()` hoặc bất kỳ reflection nào → **NameError** |
| B2 | `ByteTrack` **đã deprecated từ supervision 0.28, sẽ bị xoá ở 0.31** | `ai/tracker.py:2,6`; `pyproject.toml` ghim `supervision>=0.25` **không có trần** | Một lần `uv sync` sau này là **vỡ pipeline AI**. Thay bằng `ByteTrackTracker` (`pip install trackers`), method đổi tên `update_with_detections()` → `update()` |
| B3 | Ngưỡng cấm thi **hardcode `15.0/20.0`** | `report_service.py:104-105` | Đổi `WARNING_ABSENCE_PERCENT`/`MAX_ABSENCE_PERCENT_EXAM_BAN` ở `/admin/settings` (đã seed ở `sql/02_seed.sql:95-96`) **không** làm báo cáo cấm thi thay đổi |
| B4 | **Khoá Kiosk hardcode + so sánh không hằng thời gian** | `deps_auth.py:98` — `valid_keys = {S.kiosk_api_key, "kiosk-secret-key-2026", "detect-ai-kiosk-secret-key-2026"}` | Đặt khoá riêng vẫn bị 2 khoá mặc định mở cửa. Dùng `secrets.compare_digest(x, S.kiosk_api_key)` |
| B5 | **2 thread daemon chạy vô hạn ngay khi import** | `main.py:15` → `routes_camera.py:4` → `rtsp_worker.py:98` `worker = RtspWorker()` → `__init__` mở 2 thread (`:27-28`) | Mọi lần khởi động backend — kể cả khi không ai dùng RTSP — đều có 2 thread quay `time.sleep(0.1)`. Xoá router legacy là hết |
| B6 | **Không mount `/static`** (grep `app.mount` = **0 hit**) | `core/supabase.py:88` trả `/static/storage/...`; `proof-preview-modal.tsx:203` dùng thẳng làm `<img src>` | **Ảnh minh chứng nghỉ phép không hiển thị ở chế độ offline** |
| B7 | **Hai sổ đăng ký khuôn mặt** | `routes_students.py:46-49` ghi `students.embedding`; `face_store.py:61-74` **chỉ đọc** `student_profiles.face_embedding` | Sinh viên thêm qua `/api/students` **không bao giờ được nhận diện** |
| B8 | `except (JWTError, Exception)` — nuốt **mọi** lỗi, kể cả lỗi cấu hình | `core/security.py:45` | Token sai cấu hình `JWT_SECRET` bị báo nhầm thành "token hết hạn" |
| B9 | **Không có `app.add_exception_handler` nào** trong toàn backend | grep = 0 hit | Buộc phải viết **11 chỗ pre-check thủ công** để bù (xem §4.4) |
| B10 | **2 nguồn sự thật về schema**: `sql/01_schema.sql:7-17` tạo **ENUM native PG** trong khi ORM khai `native_enum=False` | `models/attendance_v2.py:48-57` | Tuỳ đường tạo bảng mà ra schema vật lý khác nhau |
| B11 | Drift schema **đã xảy ra thật**: `init_db()` phải vá tay | `core/database.py:44-47` — `ALTER TABLE students ADD COLUMN photo` | Không có Alembic → mọi thay đổi model phải vá tay |
| B12 | Kiểm tra trùng đơn nghỉ **không có ràng buộc DB tương ứng** | `routes_leave_requests.py:137-148` | 2 request đồng thời cùng tạo đơn — race thật (9 chỗ pre-check khác đều đã có unique constraint) |

---

## 2. Phát hiện MỚI (tài liệu cũ chưa có)

1. **`ByteTrack` deprecated** (B2) — rủi ro vỡ pipeline trong tương lai gần, `pyproject.toml` không ghim trần.
2. **`rtsp_worker` chạy 2 thread ngay lúc import** (B5) — chi phí thật ở mọi lần khởi động.
3. **`core/config.py:59-81` có 30 alias `X = S.x` không làm gì cả.** Vừa thừa, vừa tạo **hai phong cách**
   truy cập cấu hình (`from ..core.config import C; C.YOLO_CONF` trong `ai/` vs `from ..core.config import YOLO_CONF`).
   Xoá 30 dòng, dùng thẳng `S.`. Kèm theo: `config.py:25-27` định nghĩa property `jwt_expire_minutes`
   **trùng nghĩa** với field `jwt_access_token_expire_minutes`, và `security.py:30,34,42` dùng
   `getattr(S, "jwt_algorithm", "HS256")` dù `config.py` đã có sẵn field → 3 `getattr` thừa.
4. **`require_role` là factory → Double-guard thật sự tốn 2 lần truy vấn DB.**
   `deps_auth.py:79-91` trả về closure mới mỗi lần gọi; FastAPI cache dependency theo **callable**,
   nên guard ở router và guard ở endpoint **không dùng chung** `get_current_user`.
   **6 endpoint bị kiểm tra 2 lần**: cả 5 endpoint của `routes_teacher.py` (`router` `:24` + `:103,142,281,358,389`)
   và `routes_admin_reports.py` (`:17` + `:26`) → **2 lần decode JWT + 2 query DB mỗi request**.
   Sửa 1 dòng: khai singleton ở module — `require_teacher = require_role("TEACHER")`.
5. **12/45 endpoint không có xác thực nào**: toàn bộ `routes_students.py` (5 endpoint, gồm **CRUD khuôn mặt**
   và phục vụ file ảnh), `routes_attendance.py` (2), `routes_camera.py` (4), `routes_kiosk.py` (1).
6. **`routes_admin_academic.py:132-138` COUNT từng lớp (N+1)** — trong khi **chính repo đã có cách đúng**:
   `routes_teacher.py:106-115` dùng `outerjoin + group_by`.
7. **`report_service.py:148-162` N+1 toàn trường**: gọi `calculate_class_exam_ban` trong vòng lặp lớp
   (4 query/lớp).
8. **`evaluation_service.py` có 2 chuỗi `if/elif` 5 nhánh y hệt nhau** để map status→điểm
   (`:118-133` và `:149-183`) → thay bằng 1 dict; đồng thời `select(StudentProfile)` nằm **trong vòng lặp**
   từng attendance (`:112-113`).
9. **`ai/pipeline.py` mang máy móc đồng bộ phức tạp không cần thiết**: `_gen` counter + `_pending` dict +
   `add_done_callback` + vòng đời `ThreadPoolExecutor` dựng lại trong `reset()`
   (`:22-41`, `:53-60`, `:94-102`). Vì `ws_handler.py:57` đã gọi `asyncio.to_thread`, có thể chuyển
   sang `asyncio.create_task` + `Semaphore(1)` trong async — bỏ được `_gen`, `_pending`, callback và
   cả một lớp lỗi race.
10. **`frontend` không có `loading.tsx` / `error.tsx` / `not-found.tsx`** (21 file route, 0 file đặc biệt).
    Hệ quả: markup spinner **lặp 3 nơi** (`app-shell.tsx:37-46`, `role-guard.tsx:25-34`, `app/page.tsx:28-32`)
    và **không có error boundary nào**.
11. **Map vai trò→trang chủ lặp 4 lần**: `app/page.tsx:15-20`, `login/page.tsx:20-22`, `login/page.tsx:42-50`,
    `role-guard.tsx:43-48` → 1 hằng `ROLE_HOME`.
12. **`pyproject.toml` để lẫn dependency runtime và dev**: `pytest`, `pytest-asyncio` (test) và
    `roboflow` (chỉ dùng trong `training/prepare_dataset.py`) nằm trong `dependencies` → mọi lần deploy
    kéo theo chúng. Tách `[dependency-groups]` / extras `[training]`.

---

## 3. Frontend — chi tiết

### 3.1 Số liệu đo được

| Chỉ số | Số lượng | Ghi chú |
|---|---|---|
| `useState` | **206** field / 35 `useEffect` | `admin/academic/page.tsx` một mình **31 `useState`** |
| Trang tự viết loading/error + `useEffect` + `try/catch` | **13 đầy đủ + 2 biến thể** / 19 file | `admin/academic:47,54,73,96,117,136` (3 cờ loading) |
| `<table>` viết tay | **13** ở 11 file | Chỉ `app/reports/page.tsx:3` (trang chết) dùng TanStack Table |
| Modal `fixed inset-0` | **8** | `createPortal` **0**, `Escape` **0**, `role="dialog"` **0**, `aria-modal` **0**, `tabIndex` **0** |
| `<form>` | 11, trong đó **9 form dùng 44 `useState` field** | `react-hook-form` dùng ở đúng **1** form (`students/page.tsx:3` — trang chết) |
| Map status→màu / badge span | **9** định nghĩa, **24** badge span | `student/attendance:115-152` ≈ `live:154-193` ≈ `leave-requests:92-115` ≈ `teacher/reports:171-195` |
| Hàm format ngày tự viết | **8** + 4 lần `toISOString().split("T")[0]` | `padStart/getMonth()+1` |
| `window.confirm` / `alert` | **7** ở 5 file | `academic:177,225,239`, `admin/users:86`, `students:64`, `teacher/classes:88`, `teacher/reports:165` |
| `setInterval` + vòng lặp tự hẹn giờ | **5 + 2 + 3 timer hack** | `topbar:41` (30s), `live:89` (5s), `teacher/reports:278` (`setTimeout 50ms` để ép refetch) |
| `catch (err: any)` | **39** | + 29 lần tự gọi lại `load()` sau mutation |

### 3.2 Việc cần làm

1. **Tầng dữ liệu** (ưu tiên 1): thêm **SWR** hoặc **@tanstack/react-query**; 13 trang chuyển sang
   `useQuery`/`useMutation` → xoá loading/error/refetch thủ công, tự cache + tự invalidate.
   Thay 3/5 `setInterval` bằng `refetchInterval`. **~170 dòng.**
2. **`<DataTable>` + `<TableState>` + `<EmptyState>`**: gom 13 bảng, 12 dòng `colSpan`, 12 khối loading,
   13 empty-state. Dùng **@tanstack/react-table** (đã cài). **~380 dòng.**
3. **`<Modal>` trên Radix Dialog** cho 8 modal → portal, Escape, focus-trap, `aria-modal`, `role="dialog"`.
   Đây là **khoảng trống a11y lớn nhất** của dự án (0 affordance bàn phím/AT trong toàn bộ 31 file `.tsx`).
   **~240 dòng + sửa a11y.**
4. **react-hook-form + zod** cho 9 form → bỏ 44 `useState` field + validate tay. **~250 dòng.**
5. **`lib/format.ts` + `lib/status.ts` + `<StatusBadge>`**: gom 8 formatter, 9 map màu, 24 badge.
   **~260 dòng.**
6. **`lib/api.ts`**: 767 dòng / 83 export viết tay, khối parse lỗi copy 4 lần
   (`:83-95`, `:110-119`, `:752-761`, `:842-851`), 2 wrapper `fetch` song song
   (`authFetch` `:57-98` vs `j` `:785-789` không gửi auth) + `login`/`recordKioskAttendance` tự gọi `fetch`.
   → 1 `apiFetch` + sinh type từ `/openapi.json` bằng **openapi-typescript**. **767 → ~180 dòng.**
   Ngoài ra khối legacy `:780-804` gọi `/api/...` **thiếu tiền tố `/v1`** — chỉ 3 trang chết dùng.
7. **Xoá `app/attendance`, `app/students`, `app/reports`** (438 dòng): grep `href="/attendance"|href="/students"|href="/reports"`
   = **0 hit**; `sidebar.tsx:35-57` không có mục nào. `app/attendance/page.tsx:12-58,150-159` là **bản sao
   trùng lặp** của `camera-feed.tsx:105-200,308-335` (cùng getUserMedia + nội suy box + canvas + JPEG qua WS).
   Xoá 2 trang này **tự động gỡ luôn** `@tanstack/react-table` và `react-hook-form` khỏi danh sách "cài mà không dùng".
8. **`app/loading.tsx`, `app/error.tsx`, `app/global-error.tsx`** + 1 `<Spinner>` + hằng `ROLE_HOME`. **~40 dòng.**
9. **Toast + `<ConfirmDialog>`** thay 7 `window.confirm`/`alert` (chặn main thread, không style được,
   `alert` đặc biệt khó chịu trên màn Kiosk tự làm mới). **~20 dòng + UX.**
10. **`admin/academic/page.tsx` (805 dòng / 31 `useState`) gánh 4 nghiệp vụ** (lớp, sinh viên trong lớp,
    lịch học, 3 modal) → tách `useClasses()`, `useSchedules()`, `<ClassesTable>`, `<ClassStudentsModal>`.
    Lưu ý bug tiềm ẩn: `classesPage` (`:44`) chỉ được reset về 1 khi đổi từ khoá (`:350`) —
    **không có UI chuyển trang**, nên phân trang lớp học thực tế không dùng được.
11. **Dependency cần thêm**: `swr` hoặc `@tanstack/react-query`, `@radix-ui/react-dialog` (hoặc `@headlessui/react`),
    `zod`, `clsx` + `tailwind-merge` (hiện nối `className` bằng template string khắp nơi),
    `date-fns`, `sonner`, và **một tầng test** (`vitest` + `@testing-library/react` / `@playwright/test` —
    frontend hiện **không có test nào**).

### 3.3 `camera-feed.tsx` — đánh giá riêng

372 dòng, nhưng **không nên "đơn giản hoá" bằng cách thay thư viện**:
canvas overlay nội suy box + vòng lặp gửi frame là đặc thù và đã viết đúng (throttle, `stopRequestedRef`,
xử lý `visibilitychange`). Chỉ nên: (a) gom logic vào `hooks/use-detection-stream.ts` để dùng chung sau khi
xoá trang `/attendance` trùng, (b) thay 3 chỗ `setTimeout` bằng `requestVideoFrameCallback`/`refetchInterval`.
Đây là **code inference-critical — làm cuối cùng**.

---

## 4. Backend — chi tiết

Quy mô: `api/` = **2.203 dòng / 45 endpoint**, **59 `raise HTTPException`**, 21 model Pydantic viết tay.

### 4.1 Xác thực & phân quyền

- `require_role(...)` xuất hiện **20 lần**: 1 định nghĩa, **6 ở cấp router** (đúng), **13 ở cấp endpoint** (thừa).
- **6 endpoint bị double-guard** → 2 lần decode JWT + 2 query DB/request (xem §2.4).
- **5 khối 401 giống nhau** ở `deps_auth.py:23-27, 31-35, 39-43, 63-67, 70-74` → 1 hằng
  `credentials_exception` (đúng mẫu trong docs FastAPI) hoặc `OAuth2PasswordBearer(auto_error=True)`
  để xoá luôn nhánh `if not token` (`:22-27`). **~14 dòng.**

### 4.2 Thông báo lỗi lặp

| Số lần | Chuỗi | Vị trí |
|---|---|---|
| 5 | `f"Không tìm thấy lớp học phần có ID {class_id}"` | `routes_admin_academic.py:218, 288, 308, 347, 468` |
| 3 | `f"Không tìm thấy người dùng có ID {user_id}"` | `routes_admin_users.py:299, 352, 377` |
| 3 | `"Không tìm thấy lớp học phần"` | `routes_teacher.py:149, 365, 396` |
| 3 | `"not found"` | `files.py:19`, `routes_students.py:59, 81` |
| 2 | `f"Không tìm thấy giảng viên có ID {teacher_id}"` | `routes_admin_academic.py:181, 246` |
| 2 | `"Không tìm thấy dữ liệu lớp học"` | `routes_teacher.py:378, 409` |

**22 khối** theo đúng khuôn `if not <entity>: raise HTTPException(404, ...)` → thay bằng 1 helper
`async def get_or_404(db, Model, id, detail=None)`. **~55 dòng.**

### 4.3 Serialize thủ công

**16 model khai `ConfigDict(from_attributes=True)` nhưng `model_validate` xuất hiện `0` lần trong toàn bộ
`backend/src`.** 24 chỗ dựng DTO bằng tay, **174 dòng gán field**. Ví dụ điển hình — cùng một mapping
`ClassResponse` viết **3 lần**:

```python
# routes_admin_academic.py:142-152 — y hệt ở :195-204 và :267-276
ClassResponse(id=c.id, class_code=c.class_code, course_name=c.course_name,
    teacher_id=c.teacher_id, teacher_name=teacher_name, semester=c.semester,
    total_sessions=c.total_sessions, student_count=student_cnt)
```

Các chỗ nặng khác: `routes_student_portal.py:101,143,191`; `routes_teacher.py:122,226,242,256`;
`routes_auth.py:75,84,91`; `routes_admin_users.py:107,116,123`; `routes_admin_settings.py:39,79`
(khối `:37-46` và `:77-86` **trùng y hệt nhau** ngay trong cùng 1 file).

→ Giữ `from_attributes=True`, thêm sub-model lồng nhau, dùng `@computed_field` cho field dẫn xuất
(`role_str`, `teacher_name`, `student_count`), rồi `Model.model_validate(obj)`. **~100/174 dòng.**

Ngoài ra:
- `format_leave_request` (`routes_leave_requests.py:64-92`, **29 dòng** dựng dict 20 field) rồi lại được
  chính model đó validate lại — và dùng theo **2 kiểu khác nhau**: `:252-253` `LeaveRequestResponse(**dict)`
  vs `:177` trả thẳng dict cho FastAPI validate. **~26 dòng.**
- `serialize_user` (`routes_auth.py:71-100`) vs `serialize_admin_user` (`routes_admin_users.py:103-134`):
  cùng cấu trúc 3 nhánh; 2 cặp DTO lồng nhau (`routes_auth.py:31-48` vs `routes_admin_users.py:27-45`)
  **trùng từng field**. **~25 dòng.**
- Khối eager-load `selectinload(User.role/student_profile/teacher_profile)` **copy 5 lần**
  (`deps_auth.py:45-52`, `routes_auth.py:109-119`, `routes_admin_users.py:159-166, 267-275, 286-294`)
  → 1 hằng `USER_LOAD_OPTIONS`. **~15 dòng.**

### 4.4 Phân trang & ràng buộc DB

- **4 bản copy** `count + offset + limit`: `routes_admin_academic.py:123-127`, `routes_admin_users.py:184-189`,
  `routes_leave_requests.py:236-248`, `routes_students.py:25-27`.
  **4 envelope `{items,total,page,size}` trùng nhau**: `schemas.py:11-14`, `routes_admin_academic.py:35-39`,
  `routes_admin_users.py:62-66`, `routes_leave_requests.py:52-56`.
  → `class Page(BaseModel, Generic[T])` + `paginate()` (hoặc **fastapi-pagination**). **~32 dòng.**
- **11 chỗ pre-check thủ công để bù cho ràng buộc DB đã có sẵn:**

| # | Vị trí | Ràng buộc DB đã tồn tại |
|---|---|---|
| 1 | `routes_admin_users.py:202-210` | `users.user_code` unique (`models/user.py:36`) |
| 2 | `routes_admin_users.py:212-220` | `users.email` unique (`:38`) |
| 3 | `routes_admin_users.py:306-315` | như #2 |
| 4 | `routes_admin_academic.py:162-170` | `classes.class_code` unique (`models/academic.py:27`) |
| 5 | `routes_admin_academic.py:221-231` | như #4 |
| 6 | `routes_admin_academic.py:364-377` | **`ClassStudent` PK tổng hợp** (`models/academic.py:56-61`) → trùng **không thể xảy ra** |
| 7 | `routes_teacher.py:310-329` | `uq_attendance_schedule_student` (`models/attendance_v2.py:69`) |
| 8 | `routes_leave_requests.py:137-148` | **không có** → race thật |
| 9 | `routes_admin_settings.py:63-69` | `system_settings.key` unique (`models/system_setting.py:12`) |
| 10 | `routes_students.py:38-39` | `students.code` unique (`models/student.py:10`) |
| 11 | `routes_admin_academic.py:454-459` | `CheckConstraint("start_time < end_time")` (`models/academic.py:78`) |

  → Xoá pre-check, thêm **1** `@app.exception_handler(IntegrityError)` trong `main.py` (hiện **chưa có handler nào**)
  map unique-violation → 400/409 kèm thông báo tiếng Việt; thêm partial unique index cho #8. **~56 dòng.**
  Lưu ý: mặc định là **SQLite** (`core/config.py:15`) với Postgres tuỳ chọn → upsert phải viết khả chuyển.

### 4.5 Các bản copy khác đáng gom

- **Kiểm tra lớp thuộc giảng viên ×3**: `routes_teacher.py:145-156, 361-372, 392-403` → dependency `get_owned_class`. **~38 dòng.**
- **Nạp báo cáo cấm thi ×2**: `routes_teacher.py:374-379` vs `:405-410`. **~8 dòng.**
- **`manual_override_attendance` (`routes_teacher.py:278-349`)** tự viết upsert: `if attendance_id > 0`, nhánh
  create `return att` sớm ở `:329` (bỏ qua đường update chung `:342-349`), và **cùng một kiểm tra 403 viết 2 lần**
  (`:304-308` và `:336-340`). Tách POST/PUT hoặc dùng 1 helper upsert. **~15 dòng.**
- **Response Excel dựng 2 lần**: `routes_teacher.py:416-421` và `routes_admin_reports.py:36-40` → 1 helper. **~5 dòng.**
- **`routes_leave_requests.py:99, 181, 207, 261` hardcode đường dẫn đầy đủ** thay vì `APIRouter(prefix=...)`
  như mọi module khác → 2 sub-router sẽ gom luôn 4 lần `require_role`. **~4 dòng.**
- **`routes_admin_settings.py:53`** nhận `Dict[str, Any]` rồi tự bóc `body.get("settings", body)` ở `:61`
  → `RootModel[dict[str, str]]` cho validate + OpenAPI miễn phí. **~3 dòng.**
- **Envelope `{"ok": True, ...}` ×11** không có `response_model` → 1 `OkResponse` để có schema. 0 dòng, chất lượng API.

### 4.6 Lõi AI & streaming

- **`ai/tracker.py` (9 dòng) chỉ bọc 1 lời gọi** — mà lại thiếu import và dùng class deprecated (B1, B2).
  Cách đơn giản nhất: **xoá hẳn file**, gọi trực tiếp API mới trong `pipeline.py`.
- **`ai/pipeline.py`**: xem §2.9 — bỏ `_gen`/`_pending`/callback/pool, chuyển sang async + `Semaphore(1)`. **~30 dòng + hết race.**
- **`get_shared_models()` (`pipeline.py:116-125`)** dùng `global _shared_yolo` → `functools.lru_cache(maxsize=1)`.
- **`streamers/save_queue.py` + `legacy_attendance`**: cùng một frame, Kiosk ghi **2 nơi** —
  `camera-feed.tsx:85` gọi `/api/v1/attendance/kiosk-record` (bảng thật `attendance`) **và**
  `ws_handler.py:60` → `save_queue` ghi `legacy_attendance` (`student_id` luôn NULL).
  → Chọn 1 đường ghi; nếu muốn giữ ảnh snapshot thì ghi vào bucket `snapshots` — việc này cũng lấp
  `snapshot_url` đang luôn `null` (`routes_student_portal.py:54,156`). **~35 dòng + hết ghi trùng.**
- **`face_store.decode_embedding` (`face_store.py:18-56`, 39 dòng)** đoán 4 định dạng rồi pad/cắt về 512 chiều,
  cộng thêm cache Faiss trong RAM → **pgvector** (Supabase hỗ trợ): cột `vector(512)` +
  `ORDER BY embedding <=> :v`. **~150 dòng + bỏ `faiss-cpu`.**

### 4.7 Cấu hình, bảo mật, đóng gói

- `core/config.py:59-81`: **30 alias `X = S.x` vô nghĩa** → xoá, dùng `S.` (§2.3). **~32 dòng.**
- `core/security.py`: `except (JWTError, Exception)` (B8) + 3 `getattr(S, ...)` thừa (`:30,34,42`).
- **`passlib[bcrypt]` + `bcrypt<4.1`** — ghim 2 gói chỉ để né lỗi tương thích của passlib (không còn bảo trì);
  **`python-jose`** cũng không còn bảo trì → dùng thẳng `bcrypt` (hoặc `pwdlib`) + **PyJWT**.
- `pyproject.toml`: tách `pytest`/`pytest-asyncio` sang dev-group, `roboflow` sang extras `[training]` (§2.12).
- **CORS `allow_origins=["*"]`** (`main.py:53`) — không phải vấn đề đơn giản hoá nhưng nên siết khi lên production.

---

## 5. Dữ liệu & Schema

1. **Alembic** thay cho `create_all()` + vá tay (B10, B11). Chọn **1 kiểu enum duy nhất** (native PG **hoặc**
   `VARCHAR + CHECK`), `sql/` chỉ giữ seed. **Công sức L, nhưng chặn cả một lớp bug.**
2. **`settings_repo`** dùng chung cho 5 chỗ đọc `system_settings` (`evaluation_service.py:32-57`,
   `kiosk_service.py:109-111`, `routes_admin_settings.py:34-48`, `report_service.py`) + cache ngắn
   → **sửa luôn bug B3**. **~60 dòng.**
3. **pgvector** thay JSON-string embedding trong cột `TEXT` (`models/user.py:106`,
   `routes_admin_users.py:397`, `face_store.py:18-56`). **Cần migration + backfill.**

---

## 6. Test (4.398 dòng)

- **Không có `backend/tests/conftest.py`** (glob chỉ thấy `conftest.py` trong `.venv`).
- **9 file** tự dựng `create_async_engine` + PRAGMA (`test_auth.py:23`, `test_db_models.py`, `test_admin_academic.py:21`,
  `test_evaluation_cron.py:22`, `test_e2e_flow.py:76`, `test_kiosk.py:23`, `test_leave_workflow.py:21`,
  `test_student_portal.py:18`, `test_teacher_and_reports.py:20`).
- **8 file** tự dựng ASGI client; helper auth header lặp ở 8 file.
- `seeded_data` khác nhau giữa các file là **hợp lý** (mỗi kịch bản cần dữ liệu riêng) — chỉ nên tách
  **factory** `make_user()/make_class()/make_schedule()`.
- **Giữ nguyên `test_e2e_flow.py`** — đây là lưới an toàn cho mọi refactor ở trên.
- **Số liệu nền hiện tại: `85 test` thu thập được** (`pytest tests --collect-only`).
  Frontend **không có test nào**.

---

## 7. Không nên "đơn giản hoá" (đang hợp lý)

- `services/evaluation_service.py`: thuật toán idempotent, rõ ràng, có test phủ — chỉ rút phần đọc settings
  và phần map status→điểm ra ngoài.
- `services/kiosk_service.py`: tìm ca học theo phòng ±30 phút và phân định in/out là nghiệp vụ đặc thù,
  không có thư viện thay thế.
- `services/report_service.calculate_class_exam_ban`: công thức `V = N_vắng + 0.5×N_nửa_buổi` và cơ chế
  hoàn điểm (`routes_leave_requests.py:323-361`) đúng đặc tả — chỉ sửa phần hardcode ngưỡng.
- `components/kiosk/camera-feed.tsx`: canvas overlay + nội suy box + throttle frame là đặc thù, đã viết đúng.
- `ai/yolo_uniform_detector.garments_of`: đã vector hoá bằng numpy, không cần đổi.
- SQLAlchemy 2.0 `Mapped[]`, APScheduler cron 23h59, JWT + RBAC, `RoleGuard`: lựa chọn chuẩn.
- `components/layout/*`, `lib/auth-context.tsx`: nhỏ, rõ, đúng chuẩn React Context.

---

## 8. Lộ trình đề xuất

### Giai đoạn 1 — Sửa bug & dọn rác (1 buổi, rủi ro thấp)
- Sửa **B1–B4, B8** (tracker import + ByteTrack, ngưỡng cấm thi, khoá Kiosk, `except` nuốt lỗi).
- Xoá code chết: `routes_students/attendance/camera`, `models/student|attendance(legacy)|uniform_rule`,
  `UniformRule` (0 tham chiếu), `rtsp_worker` (gỡ luôn **B5** — 2 thread thừa), 3 trang frontend chết,
  khối `api.ts:780-804`. **~1.100–1.400 dòng.**
  ⚠️ `save_queue` đang được Kiosk gọi thật → phải quyết định trước (xem §4.6).
- Xoá 30 alias trong `config.py`; mount `/static` (**B6**) + helper `mediaUrl()`.
- Thêm `backend/tests/conftest.py` (**~290 dòng**).
- **Kiểm chứng:** `pytest tests -v` (85 test) + `npm run build`.

### Giai đoạn 2 — Tầng dữ liệu & UI dùng chung (1–2 ngày)
TanStack Query/SWR + `<DataTable>` + `<Modal>` (Radix) + `<StatusBadge>` + `lib/format.ts` +
`loading/error.tsx` + toast/confirm → chuyển 13 trang theo mẫu chung; tách `admin/academic`.

### Giai đoạn 3 — Backend & dữ liệu (2–3 ngày)
`model_validate` + `@computed_field`; `get_or_404`; `require_teacher` singleton; `get_owned_class`;
`USER_LOAD_OPTIONS`; `Page[T]` + `paginate()`; `IntegrityError` handler + bỏ 11 pre-check;
`settings_repo`; Excel bằng pandas/xlsxwriter; `apiFetch` + openapi-typescript.

### Giai đoạn 4 — Kiến trúc (làm sau cùng, rủi ro cao)
Alembic + thống nhất enum; pgvector thay JSON embedding (bỏ faiss); gộp 1 đường ghi Kiosk;
refactor `ai/pipeline.py` sang async; chuyển token sang **cookie httpOnly** + `proxy.ts`
(Next 16 đã deprecate `middleware.ts`).

---

## 9. Rủi ro cần lưu ý

- **pgvector** đổi schema → cần migration + backfill; **cookie httpOnly** ảnh hưởng cả Kiosk.
- Xoá router cũ có thể phá bookmark ngoài repo → **xác nhận với chủ dự án trước khi xoá**.
- `ByteTrack` (B2): nếu chưa muốn đổi API, **ghim `supervision<0.31`** ngay để tránh vỡ âm thầm.
- Mọi refactor frontend cần **một lượt kiểm tra hình ảnh** (đặc biệt modal/dialog) vì hiện **không có test frontend**.
- `admin/academic/page.tsx` gánh 3 cờ loading + 31 `useState` → tách dần, không viết lại một lần.

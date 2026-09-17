# Rà soát Đơn giản hoá Mã nguồn — Smart Classroom (detect-ai)

> Phạm vi: toàn bộ repo (`backend/src` 4.184 dòng, `frontend/app+components+lib` ~9.527 dòng, `backend/tests` 4.318 dòng).
> Phương pháp: đọc code trực tiếp + thống kê bằng grep/đếm dòng. Mọi kết luận đều kèm `file:line` để kiểm chứng.
> Nguyên tắc: **không đề xuất thay đổi chỉ vì "thích công nghệ khác"** — chỉ nêu chỗ lặp lại, chết, hoặc tự viết thứ thư viện đã làm tốt hơn.

---

## 1. Tóm tắt điều hành — 10 việc đáng làm nhất

| # | Vấn đề | Vị trí | Cách đơn giản hơn | Công sức | Giảm |
|---|---|---|---|---|---|
| 1 | **~1.100 dòng code chết** của "đời cũ" (UI + API + model + RTSP) không còn lối vào | `frontend/app/{attendance,students,reports}`, `api/routes_{attendance,students,camera}.py`, `models/{attendance,student,uniform_rule}.py`, `streamers/rtsp_worker.py` | Xoá hẳn; giữ `ws_handler` + `ai/pipeline` + `face_store` (Kiosk đang dùng thật) | S | **-1.100 dòng** |
| 2 | Mỗi trang tự viết `useState + useEffect + setLoading + try/catch` để gọi API (12 trang) | vd `admin/academic/page.tsx:96-114`, `teacher/classes/page.tsx:38-53`, `student/attendance/page.tsx:29-44` | **TanStack Query** (`useQuery/useMutation`) lo loading/error/cache/refetch | M | -400 dòng |
| 3 | 13 bảng HTML tự viết kèm loading-row/empty-state lặp 10 file | `admin/academic:361,507,763`, `admin/users:242`, `live:436`… | 1 component `<DataTable>` trên **@tanstack/react-table** (đã cài sẵn nhưng chỉ dùng ở trang chết) | M | -500 dòng |
| 4 | `lib/api.ts` **858 dòng**, 83 export (34 type + 49 hàm/hằng) viết tay; khối parse lỗi copy 4 lần | `api.ts:83-95`, `:110-118`, `:434-443`, `:845-854` | Sinh type/client từ `/openapi.json` (**openapi-typescript** / **orval**) + 1 hàm `request()` | M | **858 → ~150 dòng** |
| 5 | Đọc `system_settings` theo 3 kiểu khác nhau; **2 ngưỡng cấm thi hardcode** | `services/report_service.py:104-105` vs `evaluation_service.py:32-57`, `kiosk_service.py:109-111` | 1 `settings_repo.get_int/get_bool` dùng chung → đồng thời **sửa bug** ngưỡng 15%/20% | S | -60 dòng + hết bug |
| 6 | Hai nguồn sự thật về schema: `sql/01_schema.sql` viết tay **song song** SQLAlchemy models; `init_db()` chỉ `create_all` (không ALTER) | `sql/01_schema.sql`, `core/database.py:42-47`, `models/attendance_v2.py:49-54` | **Alembic autogenerate** từ models, chọn 1 kiểu enum (native PG vs `VARCHAR+CHECK`) | L | hết drift schema |
| 7 | Embedding khuôn mặt lưu **JSON string trong cột TEXT** → phải viết 40 dòng đoán định dạng + pad/cắt 512 chiều + Faiss cache RAM | `models/user.py:106`, `routes_admin_users.py:397`, `face_store.py:18-56` | **pgvector** (Supabase hỗ trợ): cột `vector(512)` + `ORDER BY embedding <=> :v` | M | -150 dòng |
| 8 | 65 chỗ `raise HTTPException` thủ công + pre-check trùng lặp rồi mới INSERT | `routes_admin_academic.py:163-170,221-231,365-377`, `routes_admin_users.py:203-220` | 1 `@app.exception_handler` cho lỗi nghiệp vụ + bắt `IntegrityError` → 400/409 | S | -80 dòng |
| 9 | Tự viết phân trang 4-6 lần (`count + offset + limit + Page model`) | `routes_admin_academic.py:123-129`, `routes_admin_users.py:184-191`, `routes_leave_requests.py:236-248` | 1 dependency `Pagination` + helper `paginate()` (hoặc `fastapi-pagination`) | S | -70 dòng |
| 10 | 8 modal tự viết (không portal, không Escape, 0 aria/role) và 8 form state thủ công | `components/admin/user-form-modal.tsx:161`, `schedule-form-modal.tsx:98`, `teacher/leave-reviews/page.tsx:550` | **Radix/shadcn Dialog** + **react-hook-form + zod** (RHF đã cài nhưng chỉ dùng ở trang chết) | M | -400 dòng |

**Tổng tiềm năng: giảm khoảng 2.700–3.500 dòng (~20% codebase) mà không mất tính năng nào.**

---

## 2. Code chết — xoá được ngay, rủi ro thấp

Bằng chứng: `grep href="/attendance|/students|/reports"` trong frontend = **0 hit**; `sidebar.tsx:35-57` chỉ có `/student/*`, `/teacher/*`, `/admin/*`, `/diem-danh`; các module backend dưới đây **chỉ** được nhắc trong `main.py`.

| Thành phần | Dòng | Ghi chú |
|---|---|---|
| `frontend/app/attendance/page.tsx`, `app/students/page.tsx`, `app/reports/page.tsx` | 438 | Trang cũ, chỉ vào được bằng cách gõ URL tay |
| `backend/src/detect_ai/api/routes_students.py` (+ `api/schemas.py`) | 85 (+12) | Dùng model cũ `students`; API trùng chức năng với `/api/v1/admin/users` |
| `api/routes_attendance.py`, `api/routes_camera.py`, `streamers/rtsp_worker.py` | 135 | RTSP/ffmpeg thủ công cho trang `/attendance` đã chết |
| `models/attendance.py` (`legacy_attendance`), `models/student.py`, `models/uniform_rule.py` | 39 | `UniformRule` **0 tham chiếu** ngoài `models/__init__.py` |
| `ai/tracker.py` | 9 | Wrapper 9 dòng; dòng 8 dùng `sv.Detections` nhưng **không import** `sv` (chỉ chạy nhờ `from __future__ import annotations`) |
| Khối API legacy trong `frontend/lib/api.ts:780-804` | 25 | Gọi `/api/attendance`, `/api/students` (không phải `/api/v1`) |
| `training/*` | 2 file | CLI standalone; kéo `roboflow` vào dependency runtime → nên tách extras `[training]` |

⚠️ **Lưu ý trước khi xoá** — `streamers/save_queue.py:22-23` đang được **chính luồng Kiosk** gọi (`ws_handler.py:60`) và ghi vào `legacy_attendance` (bản ghi có `snapshot` ảnh). Nếu xoá, cần quyết định: (a) bỏ luôn tính năng log ảnh snapshot, hoặc (b) chuyển việc lưu snapshot vào `kiosk_service` + bucket `snapshots`` — điều này cũng sẽ lấp `snapshot_url` đang luôn `null` (`routes_student_portal.py:156`).

---

## 3. Frontend — chi tiết

1. **Gọi API & trạng thái**: 12 trang lặp cùng một khuôn `useState(loading/error) + useEffect + try/catch` (`admin/academic/page.tsx:96-114`, `admin/settings:54-83`, `teacher/leave-reviews:56-73`, `student/schedule:34-49`…). Chuyển sang **@tanstack/react-query**: bỏ `loading/error/refetch` thủ công, tự cache, tự invalidate sau mutation. Đây là thay đổi cho lợi ích lớn nhất ở frontend.
2. **Bảng**: 13 `<table>` tự viết ở 11 file, kèm `colSpan` loading-row và empty-state lặp. **@tanstack/react-table** đã có trong `package.json:14` nhưng chỉ dùng ở `app/reports/page.tsx:3` (trang chết).
3. **Modal**: 8 modal cùng khuôn `fixed inset-0 z-50`, không dùng portal, không đóng bằng Escape (trừ `students:87`), `aria-` = 0. Dùng **Radix Dialog** (qua shadcn/ui) hoặc **@headlessui/react**.
4. **Trạng thái & định dạng**: map `PRESENT/LATE/ABSENT → màu` lặp ở `live:126-130`, `student/attendance:65-68`, `manual-override:36-90`; badge lặp 6 nơi; format ngày/giờ bằng `padStart/getMonth()+1` ở 8 file (`student/attendance:102`, `live:141`, `conduct-points:105`…). → 1 `lib/format.ts` + `<StatusBadge>` + `STATUS_MAP` (hoặc date-fns/dayjs).
5. **Form**: `user-form-modal.tsx:22-39` 11 `useState` + validate tay; tương tự ở `admin/academic:62-76`, `leave-request-modal:59-62`. **react-hook-form** đã cài (`package.json:12`) nhưng chỉ dùng ở trang chết → dùng thật + **zod** (chưa cài) để validate.
6. **Trang nặng nhất**: `admin/academic/page.tsx` **852 dòng / 31 `useState`** gánh 4 nghiệp vụ (lớp, sinh viên trong lớp, lịch học, 3 modal). Tách thành `useClasses()`, `useSchedules()`, `<ClassesTable>`, `<ClassStudentsModal>`. Lưu ý: state `classesPage` (`:44`) chỉ được reset về 1 khi đổi từ khóa (`:350`) — **không có UI chuyển trang**, nên phân trang lớp học thực tế không dùng được.
7. **Redirect theo vai trò lặp 3 nơi**: `app/page.tsx:11-25`, `login/page.tsx:18-24,42-50`, `role-guard.tsx:43-48` → 1 hằng số `ROLE_HOME`.
8. **Tìm kiếm client lặp 5 file**, `toLowerCase().includes` 19 chỗ, không debounce; `teacher/reports:278` dùng `setTimeout(50)` để ép refetch → 1 hook `useClientFilter`.
9. **Thông báo lỗi**: 34 chỗ `err: any` ở 18 file, `alert()` (`teacher/reports:165`, `teacher/classes:88`) và `window.confirm` (`admin/users:86`, `admin/academic:177,225,239`) → toast + `ApiError` có type + `<ConfirmDialog>`.
10. **Bảo vệ route phía client**: `RoleGuard` chạy sau khi render (12 trang), token nằm ở `localStorage` (`api.ts:4-19`), không có lớp chặn phía server. Next 16 **đã deprecate `middleware.ts` → đổi tên thành `proxy.ts`** (xác nhận trong `frontend/node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md`). Muốn chặn thật ở server phải chuyển token sang **cookie httpOnly** rồi kiểm tra trong `proxy.ts` — đây là thay đổi kiến trúc, nên làm sau cùng.
11. **`topbar.tsx:30-46`** tự `fetch(HEAD /docs)` mỗi 30 giây để hiển thị trạng thái API → thay bằng 1 lần gọi `/api/health` qua Query (tự retry/refetch).
12. **Dependency**: `@tanstack/react-table` và `react-hook-form` đang gần như không dùng; thiếu `@tanstack/react-query`, `zod`, `clsx + tailwind-merge` (đang nối className bằng template string, vd `sidebar.tsx:73-77`), `date-fns`.

---

## 4. Backend — chi tiết

1. **Schema 2 nguồn**: `sql/01_schema.sql` tạo ENUM native PG (`CREATE TYPE attendance_status`…) trong khi ORM khai `native_enum=False` (`models/attendance_v2.py:49-54`) → tuỳ đường tạo bảng mà ra schema vật lý khác nhau. Thêm nữa `core/database.py:44-47` phải vá tay `ALTER TABLE students ADD COLUMN photo` — bằng chứng drift đã xảy ra thật. → **Alembic** + 1 kiểu enum duy nhất; `sql/` chỉ giữ seed.
2. **`system_settings` đọc 3 kiểu** (`evaluation_service.py:32-57`, `kiosk_service.py:109-111`, `routes_admin_settings.py:34-48`) → 1 `settings_repo` có cache ngắn. Kèm **bug thật**: `report_service.py:104-105` hardcode `15.0/20.0` nên đổi `WARNING_ABSENCE_PERCENT`/`MAX_ABSENCE_PERCENT_EXAM_BAN` ở màn hình Admin (đã seed ở `sql/02_seed.sql:95-96`) **không** làm báo cáo cấm thi thay đổi.
3. **Serialize thủ công**: 37 class Pydantic nằm rải trong 9 file route; nhiều chỗ khai `from_attributes=True` rồi vẫn gán từng field (`routes_admin_academic.py:141-152`, `routes_admin_settings.py:38-46` và lặp lại y hệt ở `:78-86`) → dùng `model_validate()` + `@computed_field`, gom DTO về `api/dto.py`; `serialize_user` (`routes_auth.py:31-100`) và `serialize_admin_user` (`routes_admin_users.py:27-134`) gần như trùng nhau.
4. **Kiểm tra tồn tại & quyền lặp**: chuỗi `"Không tìm thấy lớp học phần"` copy 6 lần (`routes_admin_academic.py:216,286,306,345,466,521`); kiểm tra lớp thuộc giảng viên copy 3 lần (`routes_teacher.py:145-156,361-372,392-403`) → `get_or_404()` + dependency `require_owned_class`.
5. **Phân quyền 2 tầng**: router đã có `dependencies=[Depends(require_role(...))]` nhưng từng endpoint lặp lại y hệt (`routes_teacher.py:24` vs `:103,142,281,358,389`; `routes_admin_reports.py:17` vs `:26`) → chỉ giữ tầng router.
6. **N+1**: `report_service.py:148-162` gọi `calculate_class_exam_ban` trong vòng lặp lớp (4 query/lớp); `routes_admin_academic.py:132-138` COUNT từng lớp — trong khi **cùng repo đã có cách đúng** (`routes_teacher.py:106-115` dùng `outerjoin + group_by`).
7. **Supabase Storage tự viết**: `core/supabase.py:35-83` tự ghép URL, tự set header, tự fallback đĩa. Fallback trả `/static/storage/...` nhưng `main.py` **không mount StaticFiles** (grep `app.mount` = 0) và frontend dùng thẳng URL đó làm `<img src>` (`proof-preview-modal.tsx:203`) → **ảnh minh chứng không hiển thị ở chế độ offline**. → dùng `storage3/supabase-py`, hoặc tối thiểu mount `/static` + 1 helper `mediaUrl()` ở frontend.
8. **Excel styling tay**: `report_service.py:165-297` (~130 dòng `PatternFill/Font/Border`, merge cứng `"A1:I1"`, tự đo `max_len`) → `pandas.DataFrame.to_excel(engine="xlsxwriter")` + `add_table()/set_column` (~25 dòng), hoặc `NamedStyle` của openpyxl.
9. **Kiosk ghi 2 nơi**: cùng một frame, `camera-feed.tsx:85` gọi `/api/v1/attendance/kiosk-record` (bảng thật `attendance`) **và** `ws_handler.py:60` → `save_queue` ghi `legacy_attendance` (`student_id` luôn NULL). → chọn 1 đường ghi.
10. **Hai sổ đăng ký khuôn mặt**: `routes_students.py:46-49` ghi `students.embedding` (bytes) rồi `face_store.reload()`, nhưng `face_store.py:61-74` **chỉ đọc** `student_profiles.face_embedding` → sinh viên thêm qua `/api/students` không bao giờ được nhận diện; đồng thời phải viết `decode_embedding` đoán 4 định dạng (`face_store.py:18-56`).
11. **Auth**: `pyproject.toml` ghim `passlib[bcrypt]` + `bcrypt<4.1` chỉ để né lỗi tương thích của passlib (không còn bảo trì) và dùng `python-jose` (không còn bảo trì) → gọi thẳng `bcrypt` hoặc `pwdlib`; thay bằng `PyJWT`. `core/security.py:45` `except (JWTError, Exception)` nuốt mọi lỗi (kể cả lỗi cấu hình); các `getattr(S, ...)` ở `:30,34,42` là dư vì `config.py` đã có sẵn field + property trùng nghĩa.
12. **Kiosk API key có backdoor**: `deps_auth.py:98` luôn chấp nhận `"kiosk-secret-key-2026"` và `"detect-ai-kiosk-secret-key-2026"` dù đã cấu hình key riêng → chỉ nên `secrets.compare_digest(x, S.kiosk_api_key)`.
13. **Upsert thủ công**: `routes_teacher.py:284-334` tự tìm/tạo `Attendance` dù đã có `uq_attendance_schedule_student` → dùng `insert(...).on_conflict_do_update(...)` (PG).
14. **Chuẩn hoá vector lặp 3 lần** trong `ai/face_recognizer.py` (`:50`, `:73`, `:80-83`) trên nền faiss → normalize 1 lần + `IndexFlatIP`; nếu dưới ~10k sinh viên thì bỏ hẳn `faiss-cpu` cũng đủ nhanh.

---

## 5. Test (4.318 dòng)

- `test_session_maker` (khởi tạo SQLite in-memory + PRAGMA) **lặp ở 8 file**, `client` fixture lặp 5 file, helper auth header lặp 4 file → gom vào `backend/tests/conftest.py`, ước giảm **~290 dòng** mà không đổi hành vi test.
- Các `seeded_data` khác nhau là hợp lý (mỗi kịch bản cần dữ liệu riêng), nhưng nên tách **factory** dùng chung (`make_user()`, `make_class()`, `make_schedule()`) để mỗi file chỉ khai phần khác biệt.
- Giữ nguyên: bộ E2E `test_e2e_flow.py` (đi qua HTTP thật) — đây là lưới an toàn cho mọi refactor ở trên.

---

## 6. Không nên "đơn giản hoá" (đang hợp lý)

- `services/evaluation_service.py`: thuật toán idempotent, rõ ràng, có test phủ 9 case — chỉ nên rút phần đọc settings ra ngoài.
- `services/kiosk_service.py`: logic tìm ca học theo phòng ±30 phút và phân định in/out là nghiệp vụ đặc thù, không có thư viện thay thế.
- Công thức cấm thi và cơ chế hoàn điểm (`report_service`, `routes_leave_requests.py:323-361`): đúng đặc tả, giữ nguyên (chỉ sửa phần hardcode ngưỡng).
- SQLAlchemy 2.0 `Mapped[]` models, APScheduler cron 23h59, JWT + RBAC: đều là lựa chọn chuẩn, không cần thay.
- `RoleGuard` (UI 403 + điều hướng) vẫn hữu ích kể cả khi có `proxy.ts`.

---

## 7. Lộ trình đề xuất

**Giai đoạn 1 — Dọn dẹp (1 buổi, rủi ro thấp)**
Xoá code chết mục §2 (trừ `save_queue` cần quyết định), gom `conftest.py`, thêm `lib/format.ts` + `StatusBadge`, sửa 3 bug nhỏ (ngưỡng cấm thi, kiosk key hardcode, `tracker.py` thiếu import).
Kiểm chứng: `pytest tests -v` (84 test) + `npm run build`.

**Giai đoạn 2 — Chuẩn hoá frontend (1-2 ngày)**
Thêm TanStack Query + DataTable + Dialog + react-hook-form/zod; chuyển 12 trang theo mẫu chung; tách `admin/academic`.

**Giai đoạn 3 — Backend & dữ liệu (2-3 ngày)**
`settings_repo` + exception handler + pagination dependency + DTO chung; `storage3` + mount `/static`; Alembic; (tuỳ chọn) pgvector thay JSON embedding + bỏ faiss.

**Rủi ro cần lưu ý**: pgvector đổi schema (cần migration + backfill); chuyển token sang cookie httpOnly ảnh hưởng cả Kiosk; xoá route cũ có thể phá bookmark ngoài repo — nên xác nhận với chủ dự án trước khi xoá.
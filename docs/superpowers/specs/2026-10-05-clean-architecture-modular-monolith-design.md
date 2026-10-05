# Clean Architecture + Modular Monolith — Design

Ngày: 2026-10-05. Phạm vi: full-stack. Chiến lược: strangler từng module. Hướng: module dọc (hướng 1).

## 1. Kiến trúc mục tiêu

```
backend/src/detect_ai/
  shared/kernel/          # config, db, security, timeutil, pagination, errors
  modules/<m>/
    domain/               # entities thuần + policies (không SQLAlchemy, không FastAPI)
    application/          # ports (Protocol) + use_cases (1 file = 1 ca sử dụng)
    infrastructure/       # models SQLAlchemy + repos + adapters (DB, storage, AI)
    presentation/         # routes.py, schemas.py, deps (chỉ FastAPI + gọi use-case)
    public.py             # API công khai cho module khác (re-export whitelist)
    tests/
frontend/
  features/<module>/      # components, hooks, api-client, types của module
  app/                    # chỉ routing mỏng: import từ features/
```

Quy tắc biên:

- Cross-module chỉ qua `modules/<m>/public.py`. Cấm `from modules.X.infrastructure import ...`.
- `domain/`, `application/` cấm import `sqlalchemy`, `fastapi`, `cv2`, `onnxruntime`.
- Mỗi module sở hữu schema + router riêng; `main.py` chỉ `include_router` + lifespan + middleware.
- `recognition` là module hạ tầng AI: module khác gọi qua ports (`FacePort`, `LivenessPort`, `UniformPort`), không gọi engine trực tiếp.

## 2. Map dời code (backend)

| Module | Nhận từ cũ |
|---|---|
| identity | `api/routes_auth`, `routes_admin_users`, `models/user`, `core/security`, `services/settings_repo` (user prefs) |
| academic | `api/routes_admin_academic`, `models/academic`, `services/settings_repo` (học vụ) |
| attendance | `api/routes_teacher` (điểm danh), `routes_kiosk`, `routes_kiosk_ws`, `models/attendance_v2`, `services/face_service`, `services/image_service` |
| evaluation | `api/routes_evaluation`, `domain/policies/evaluation_policy`, `exam_ban_policy`, `services/evaluation_service`, `models/point_ledger` |
| leave | `api/routes_leave_requests`, `application/use_cases/review_leave`, `models/leave_request` |
| reporting | `api/routes_admin_reports`, `services/report_service` |
| recognition | toàn bộ `recognition/*` + `ai/*` + `training/*` (engine, config, gallery, liveness, uniform) |
| shared/kernel | `core/*`, `api/helpers`, `dto`, `file_urls`, `files`, `rate_limit`, `models/system_setting`, `services/storage_service`, `services/image_service` (phần generic) |

Thứ tự strangler: `shared/kernel` → `identity` → `leave` → `academic` → `evaluation` → `reporting` → `attendance` → `recognition`. Kiosk/WS và AI engine dời cuối vì ràng buộc realtime.

Mỗi PR: 1 module, giữ nguyên response JSON + URL prefix. Test cũ xanh mới merge.

## 3. Frontend + luật kiểm soát

```
features/identity/    # login, me, users admin, role-guard, token client
features/academic/    # admin academic, schedule-form, user-form modals
features/attendance/  # teacher classes/live/kiosk, student attendance/schedule
features/evaluation/  # conduct-points, teacher reports
features/leave/       # leave-requests student + teacher reviews + modal
features/reporting/   # admin reports
features/recognition/ # face-detector lib, kiosk WS hook, camera components
features/shell/       # app-shell, ui/*, api.ts core, data-table
app/                  # page.tsx mỏng: re-export/compose từ features/
```

Enforce bằng lint + CI, không chỉ convention:

- Backend: script `check_bounds.py` — quét `from modules.<a>...` trong module `<b>`, fail nếu không qua `public.py`; quét import cấm (`sqlalchemy` trong domain/application/presentation, `fastapi` trong domain/application).
- Frontend: eslint `no-restricted-imports` — `features/<a>` cấm import sâu `features/<b>/*`, chỉ qua `features/<b>/index.ts`.
- `public.py` / `index.ts` là whitelist duy nhất; thêm export = quyết định kiến trúc, review kỹ.

## 4. Kiểm thử + tiêu chí xong

Theo tầng:

- `domain/`: unit thuần, không DB (mẫu: `decide_attendance`).
- `application/`: use-case với ports fake (in-memory repo), assert logic + gọi ports.
- `infrastructure/`: repo test với DB thật (sqlite/testcontainer), 1-2 case đại diện.
- `presentation/`: test API giữ contract — reuse test cũ (`tests/test_*.py` dời theo module), assert status + JSON shape.
- E2E: giữ `test_e2e_flow.py` ở root, chạy cuối mỗi PR strangler.

Definition of Done:

- Không còn `api/routes_*`, `services/*`, `models/*` cũ (trừ shim re-export tạm thời có deadline xóa).
- `check_bounds.py` xanh, eslint xanh, pytest xanh, tsc xanh.
- API contract unchanged: diff OpenAPI schema trước/sau = rỗng.
- Xóa shim, xóa code chết (`streamers/` đã rỗng, `ai/bench_*` dời vào `recognition/bench/`).

# Fix Modular Monolith Violations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xóa toàn bộ vi phạm biên modular-monolith, code chết/trùng lặp, giữ nguyên API contract + DB schema.

**Architecture:** Strangler hoàn tất Task 9: gom storage về 1 mối trong `shared/kernel`, cắt chiều ngược `recognition → academic/attendance`, dời engine cũ vào `modules/recognition/infrastructure`, siết `check_bounds.py`, xóa `streamers/`, legacy models, orphan routes, untracked bench rác.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, pytest + pytest-asyncio, Next.js App Router, TypeScript, ESLint.

**Spec:** `docs/superpowers/specs/2026-10-05-clean-architecture-modular-monolith-design.md`

## Global Constraints

- Giữ nguyên response JSON và URL prefix mọi endpoint trong suốt quá trình.
- Giữ nguyên DB schema — chỉ dời file models, không sửa cột/bảng.
- Mỗi task kết thúc bằng test xanh (`pytest`, `tsc`) mới được commit.
- Không thêm dependency mới — chỉ dùng stdlib + package đã có.
- `domain/`, `application/` cấm import `sqlalchemy`, `fastapi`, `cv2`, `onnxruntime`.
- Cross-module chỉ qua `modules/<m>/public.py`. Cấm `from modules.X.infrastructure import ...`.
- `recognition` là module hạ tầng AI: module khác gọi qua ports (`FacePort`, `LivenessPort`, `UniformPort`), không gọi engine trực tiếp.

## Review Focus

- Kiosk WS frame bận thì drop ở tầng WS thay vì xếp hàng — sửa cycle import không được đổi sang await DB trong hot-path mỗi ~450ms.
- `routes_files.py` hiện không mount trong `main.py` nhưng `supabase.py` trả URL `/api/v1/files/...` — xóa nhầm là 404 minh chứng/avatar hàng loạt.
- `AttendanceRecord/legacy_attendance` FK `students.id` sai schema — xóa phải kèm xóa `streamers/save_queue.py`引用, không để migration quét nhầm bảng.
- `commit_decisions` batch SELECT 1 lần (N+1 → 1 query) — tách cycle không được tách thành query mỗi SID.
- `is_manual_override = TRUE` kiosk không được ghi đè — refactor checkin phải giữ gate này, test contract kiosk phải xanh.

---

### Task 0: Baseline + siết check_bounds (fail trước, pass sau)

**Files:**
- Modify: `backend/scripts/check_bounds.py`
- Test: `backend/tests/test_arch_bounds.py`

**Interfaces:**
- Consumes: không (task gốc).
- Produces: `check_bounds()` exit 0 chỉ khi 0 violation; quy ước `modules/<m>/public.py` là whitelist duy nhất.

- [ ] **Step 1: Chạy baseline, ghi lại violations hiện tại**

Run: `cd backend && python scripts/check_bounds.py`
Expected: PASS giả (đang có `TEMP_ALLOW` che 3 file + không quét `main.py`).

- [ ] **Step 2: Viết test fail cho lỗ hổng bounds**

```python
# backend/tests/test_arch_bounds.py — thêm 2 case:
import subprocess, sys
def test_bounds_catches_main_deep_import():
    # main.py import modules.*.presentation trực tiếp phải bị coi là violation
    # (hiện script chỉ quét modules/, bỏ sót main.py)
    assert True  # agent thay bằng assert gọi check_bounds(strict=True) != 0 khi main còn deep import
def test_no_temp_allow():
    src = open("scripts/check_bounds.py", encoding="utf-8").read()
    assert "TEMP_ALLOW" not in src or "leave/application/review" not in src
```

- [ ] **Step 3: Chạy test, xác nhận fail**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_arch_bounds.py -v`
Expected: FAIL (TEMP_ALLOW còn, main.py chưa quét).

- [ ] **Step 4: Siết script tối thiểu**

```python
# backend/scripts/check_bounds.py — diff tối thiểu:
FORBIDDEN = {
    "domain": ("sqlalchemy", "fastapi", "cv2", "onnxruntime"),
    "application": ("sqlalchemy", "fastapi", "cv2", "onnxruntime"),
    "presentation": ("sqlalchemy",),  # thêm dòng này
}
# xóa TEMP_ALLOW hoàn toàn, quét thêm main.py + api/ + shared/:
# ROOT quét modules/, thêm SCAN_EXTRA = [src/detect_ai/main.py]
```

- [ ] **Step 5: Chạy lại sau khi các Task 1-3 xong, xác nhận pass**

Run: `cd D:/Android-APP/detect-ai && python backend/scripts/check_bounds.py`
Expected: PASS (exit 0). Chưa pass thì không commit Task 0.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/check_bounds.py backend/tests/test_arch_bounds.py
git commit -m "chore(arch): siết check_bounds, trả nợ TEMP_ALLOW"
```

---

### Task 1: Storage single-source (3 bản → 1)

**Files:**
- Modify: `backend/src/detect_ai/shared/kernel/supabase.py` (giữ, nguồn duy nhất)
- Modify: `backend/src/detect_ai/shared/kernel/storage_service.py` (wrapper mỏng, không import ngược)
- Modify: `backend/src/detect_ai/application/adapters/storage_adapter.py` (dời validate vào đây hoặc xóa, chỉ giữ 1)
- Modify: `backend/src/detect_ai/modules/leave/presentation/routes.py:11` (đổi import sang kernel)
- Test: `backend/tests/test_storage_local_only.py`, `backend/tests/test_db_models.py::test_supabase_storage_local_fallback`

**Interfaces:**
- Consumes: `shared.kernel.supabase.supabase_storage` (đã có).
- Produces: `upload_leave_proof_bytes(data, content_type, filename) -> str | None` — 1 định nghĩa duy nhất, routes gọi qua đây.

- [ ] **Step 1: Viết test fail cho import ngược**

```python
def test_storage_no_reverse_import():
    src = open("src/detect_ai/shared/kernel/storage_service.py", encoding="utf-8").read()
    assert "application.adapters" not in src  # hiện dòng 8 import ngược
```

- [ ] **Step 2: Chạy, xác nhận fail**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_storage_local_only.py -v`
Expected: FAIL ở assert mới (chưa sửa), test cũ PASS.

- [ ] **Step 3: Sửa tối thiểu**

```python
# storage_service.py: xóa dòng 8 `from detect_ai.application...`,
# import từ .supabase + validate local:
from .supabase import supabase_storage
# upload_leave_proof_bytes dời hẳn vào storage_service.py, storage_adapter.py để shim:
# application/adapters/storage_adapter.py:
from detect_ai.shared.kernel.storage_service import *  # noqa: F401,F403  # ponytail: shim, xóa Task 3
```

```python
# modules/leave/presentation/routes.py:11 đổi:
from detect_ai.application.adapters.storage_adapter import upload_leave_proof_bytes
# → thành:
from detect_ai.shared.kernel.storage_service import upload_leave_proof_bytes
```

- [ ] **Step 4: Chạy test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_storage_local_only.py tests/test_db_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/shared/kernel/storage_service.py backend/src/detect_ai/application/adapters/storage_adapter.py backend/src/detect_ai/modules/leave/presentation/routes.py
git commit -m "refactor(arch): storage single-source về shared/kernel"
```

---

### Task 2: Cắt cycle recognition ↔ attendance/academic

**Files:**
- Modify: `backend/src/detect_ai/modules/recognition/infrastructure/enroll.py:63-71`
- Modify: `backend/src/detect_ai/modules/recognition/infrastructure/gallery.py:23-29`
- Modify: `backend/src/detect_ai/modules/recognition/infrastructure/service.py:116-119`
- Modify: `backend/src/detect_ai/modules/attendance/application/checkin.py:5` (giữ, đã đúng chiều)
- Modify: `backend/src/detect_ai/modules/identity/presentation/admin_routes.py:28,381`
- Test: `backend/tests/test_recognition_v2.py`, `backend/tests/test_kiosk_guard.py`, `modules/recognition/tests/test_ports.py`

**Interfaces:**
- Consumes: `modules.recognition.public.{commit_decisions, extract_best, enroll_image}` (giữ nguyên chữ ký).
- Produces: `record_checkin(session, schedule_id, teacher_id, decisions, frame_bgr, min_gap_minutes)` — attendance gọi recognition 1 chiều, recognition không import attendance/academic nữa.

- [ ] **Step 1: Viết test cycle**

```python
def test_recognition_no_upstream_import():
    import pathlib
    for p in ["modules/recognition/infrastructure/enroll.py",
              "modules/recognition/infrastructure/gallery.py",
              "modules/recognition/infrastructure/service.py"]:
        src = pathlib.Path(f"src/detect_ai/{p}").read_text(encoding="utf-8")
        assert "modules.academic" not in src, p
        assert "modules.attendance" not in src, p
        assert "modules.identity" not in src, p
```

- [ ] **Step 2: Chạy, xác nhận fail**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest src/detect_ai/modules/recognition/tests/test_ports.py -v`
Expected: test mới FAIL (hiện enroll/gallery/service còn import ngược).

- [ ] **Step 3: Sửa tối thiểu (inject, không query ngược)**

```python
# enroll.py: xóa block try ClassStudent/bump_version trong enroll_image,
# thay bằng callback param:
async def enroll_image(db, user_id, img_bgr, source="avatar", engine=None, on_enrolled=None):
    # ... giữ nguyên đến db.refresh(row)
    if on_enrolled is not None:
        try: await on_enrolled(user_id)
        except Exception: pass
    return row
# caller (identity/admin_routes) truyền on_enrolled=bump class — academic query nằm ở caller, không ở infra.
```

```python
# gallery.py: xóa `from detect_ai.modules.academic.public import ClassStudent`
# và `from detect_ai.modules.identity.public import User` ở top;
# chuyển thành TYPE_CHECKING + hàm load_gallery nhận `fetch_rows` callback.
# service.py: giữ local import hiện tại nhưng thêm comment ponytail,
# hoặc tốt hơn: checkin.py truyền `commit_fn` vào — giữ nguyên local import nếu chưa tách được (ceiling = public re-export).
```

```python
# identity/admin_routes.py:28,381 đổi concrete → port:
from detect_ai.modules.recognition.public import get_engine
_engine = get_engine("face")
# enroll_image(engine=_engine) thay vì import trực tiếp extract_best
```

- [ ] **Step 4: Chạy test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_recognition_v2.py tests/test_kiosk_guard.py src/detect_ai/modules/recognition/tests/test_ports.py -v`
Expected: PASS. `check_bounds.py` hết violation recognition.

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/modules/recognition backend/src/detect_ai/modules/identity/presentation/admin_routes.py backend/src/detect_ai/modules/attendance/application/checkin.py
git commit -m "refactor(arch): cắt cycle recognition, gọi qua ports"
```

---

### Task 3: Dời engine cũ + xóa code chết (song sinh/triple)

**Files:**
- Delete: `backend/src/detect_ai/streamers/` (`rtsp_worker.py`, `save_queue.py`, `ws_handler.py`)
- Delete: `backend/src/detect_ai/models/attendance.py` (`AttendanceRecord/legacy_attendance` FK sai)
- Delete: `backend/src/detect_ai/api/routes_attendance.py`, `routes_camera.py`, `routes_students.py` (orphan, main.py không mount)
- Delete: `backend/bench_face.py`, `bench_full.py`, `bench_http.py`, `bench_out.txt`, `check_ddl.py`, `.tmp_oldpaths.txt`, `pytest-of-vohoa/`
- Move: `backend/src/detect_ai/recognition/face_engine.py` + `_providers.py` → `modules/recognition/infrastructure/` (xóa shim ngược trong adapters/config/enroll/gallery/liveness/pipeline/uniform_engine/public)
- Move: `backend/src/detect_ai/training/label_tool.py` → `modules/recognition/infrastructure/bench/` hoặc xóa nếu chỉ là tool tay
- Move: `backend/src/detect_ai/api/routes_admin_settings.py` → `modules/reporting` hoặc `modules/identity` (quyết lúc làm, prefix giữ `/api/v1/admin/settings`)
- Test: toàn bộ `backend/tests/test_kiosk*.py`, `test_e2e_flow.py`

**Interfaces:**
- Consumes: `modules.*.public` (không đổi chữ ký).
- Produces: repo không còn `streamers/`, `models/attendance.py`, orphan routes, bench root; engine nguồn duy nhất ở `modules/recognition/infrastructure/`.

- [ ] **Step 1: Viết test guard orphan**

```python
def test_no_legacy_attendance_table():
    src = open("src/detect_ai/models/__init__.py", encoding="utf-8").read()
    assert "AttendanceRecord" not in src
def test_no_streamers_import():
    import subprocess
    r = subprocess.run(["grep", "-rn", "streamers", "src", "tests"], capture_output=True, text=True)
    assert r.stdout.strip() == "", r.stdout[:2000]
```

- [ ] **Step 2: Chạy, xác nhận fail**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_db_models.py -v`
Expected: FAIL ở guard mới (file chết còn).

- [ ] **Step 3: Xóa/dời tối thiểu (git mv + git rm)**

```bash
git rm backend/src/detect_ai/streamers/rtsp_worker.py backend/src/detect_ai/streamers/save_queue.py backend/src/detect_ai/streamers/ws_handler.py backend/src/detect_ai/models/attendance.py backend/src/detect_ai/api/routes_attendance.py backend/src/detect_ai/api/routes_camera.py backend/src/detect_ai/api/routes_students.py
git mv src/detect_ai/recognition/face_engine.py src/detect_ai/modules/recognition/infrastructure/face_engine.py
git mv src/detect_ai/recognition/_providers.py src/detect_ai/modules/recognition/infrastructure/_providers.py
# sửa 8 import `detect_ai.recognition.` → relative `.face_engine` / `._providers`
# routes_files.py: giữ + mount vào main.py (xem Task 4), không xóa
```

- [ ] **Step 4: Chạy test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_kiosk_guard.py tests/test_kiosk_window.py tests/test_e2e_flow.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore(arch): xóa streamers + legacy attendance + orphan routes, dời engine"
```

---

### Task 4: main.py qua public + trả nợ TEMP_ALLOW + mount files

**Files:**
- Modify: `backend/src/detect_ai/main.py:11-26,36,52`
- Modify: `backend/src/detect_ai/modules/evaluation/application/nightly.py:10-16` (bỏ sqlalchemy top → infra repo)
- Modify: `backend/src/detect_ai/modules/leave/application/review.py:14-20`
- Modify: `backend/src/detect_ai/modules/reporting/application/build.py:16-22` (dùng `modules/evaluation/domain/exam_ban.py`, xóa `domain/policies` import)
- Modify: `backend/src/detect_ai/modules/*/public.py` (export router: `auth_router`, `admin_router`... để main chỉ `from .modules.X.public import Y`)
- Modify: `backend/src/detect_ai/api/routes_files.py:30-35` (đổi `models.*` cũ → `modules.*.public`, mount vào main)
- Test: `backend/tests/test_arch_bounds.py`, `test_e2e_flow.py`, `test_teacher_and_reports.py`

**Interfaces:**
- Consumes: mọi `modules.<m>.public` sau Task 1-3.
- Produces: `main.py` chỉ import từ `shared.kernel` + `modules.*.public`; `GET /api/v1/files/*` 200 (không 404).

- [ ] **Step 1: Viết test main bounds**

```python
def test_main_only_public():
    src = open("src/detect_ai/main.py", encoding="utf-8").read()
    assert "modules.academic.presentation" not in src
    assert "modules.attendance.presentation" not in src
    assert "api.routes_admin_settings" not in src
    assert ".recognition._providers" not in src
```

- [ ] **Step 2: Chạy, xác nhận fail**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_arch_bounds.py -v`
Expected: FAIL.

- [ ] **Step 3: Sửa tối thiểu**

```python
# mỗi modules/<m>/public.py thêm 2 dòng cuối:
from .presentation.routes import router as _r  # noqa: F401  (tên riêng mỗi module)
# ví dụ academic/public.py: `from .presentation.routes import router as academic_router`
# main.py đổi:
from .modules.academic.presentation.routes import router as admin_academic
# → thành:
from .modules.academic.public import academic_router as admin_academic
# tương tự cho reporting/evaluation/attendance/leave/identity; settings dời xong cũng qua public.
# recognition warmup: `from .modules.recognition.public import get_engine` (port), không FaceEngine concrete.
# nightly/review/build: chuyển `select(...)` sang hàm trong infrastructure/models (repo), application chỉ gọi repo + domain policy.
# reporting/build.py:22 đổi `from detect_ai.domain.policies.exam_ban_policy import HALF_ABSENT_WEIGHT`
# → `from detect_ai.modules.evaluation.domain.exam_ban import HALF_ABSENT_WEIGHT`
```

- [ ] **Step 4: Chạy test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_e2e_flow.py tests/test_teacher_and_reports.py tests/test_arch_bounds.py -v && python ../backend/scripts/check_bounds.py`
Expected: PASS hết, check_bounds exit 0.

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/main.py backend/src/detect_ai/modules/*/public.py backend/src/detect_ai/modules/evaluation/application/nightly.py backend/src/detect_ai/modules/leave/application/review.py backend/src/detect_ai/modules/reporting/application/build.py backend/src/detect_ai/api/routes_files.py
git commit -m "refactor(arch): main qua public, trả TEMP_ALLOW, mount files"
```

---

### Task 5: Frontend features/<module> + eslint bounds (song song, không đụng backend)

**Files:**
- Create: `frontend/features/identity/`, `features/academic/`, `features/attendance/`, `features/evaluation/`, `features/leave/`, `features/reporting/`, `features/recognition/`, `features/shell/` — mỗi module có `index.ts`
- Modify: dời `frontend/lib/*`, `frontend/components/**/*` vào features tương ứng (git mv)
- Modify: `frontend/app/**/page.tsx` → mỏng (import từ features)
- Modify: `frontend/eslint.config.*` — thêm `no-restricted-imports`
- Test: `cd frontend && npx tsc --noEmit && npx eslint features/ app/`

**Interfaces:**
- Consumes: API contract backend giữ nguyên (không đổi URL/JSON).
- Produces: `features/<m>/index.ts` — `app/` chỉ import qua index.

- [ ] **Step 1: Thêm eslint rule (fail trước)**

```js
// eslint.config.*:
"no-restricted-imports": ["error", { patterns: ["features/identity/*", "features/academic/*"] }]
```

- [ ] **Step 2: Chạy, xác nhận fail**

Run: `cd frontend && npx eslint app/ features/`
Expected: FAIL (import cũ đang sâu).

- [ ] **Step 3: Dựng features + index.ts (git mv, sửa import)**

```tsx
// mỗi page.tsx chỉ còn:
export { default } from "@/features/attendance/teacher-classes-page";
```

- [ ] **Step 4: Chạy kiểm tra**

Run: `cd frontend && npx tsc --noEmit && npx eslint features/ app/ && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/features frontend/app frontend/eslint.config.* && git commit -m "refactor(arch): frontend features/<module> + eslint bounds"
```

---

### Task 6: Nghiệm thu — DoD + OpenAPI diff

**Files:**
- Create: `backend/scripts/diff_openapi.py` (so `openapi.json` main vs branch)
- Test: toàn bộ `pytest`, `tsc`, `eslint`, `check_bounds.py`

**Interfaces:**
- Consumes: toàn bộ tasks 0-5.
- Produces: báo cáo nghiệm thu khớp DoD.

- [ ] **Step 1: Chạy full suite**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 2: Chạy bounds + frontend**

Run: `python backend/scripts/check_bounds.py && cd frontend && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Đối chiếu DoD (spec §4)**

```text
- [ ] Không còn api/routes_*, services/*, models/* cũ (trừ shim có deadline)
- [ ] check_bounds xanh, eslint xanh, pytest xanh, tsc xanh
- [ ] OpenAPI diff rỗng
- [ ] streamers rỗng, ai/bench_* đã dời
```

- [ ] **Step 4: Commit cuối**

```bash
git add -A && git commit -m "chore(arch): nghiệm thu Modular Monolith (DoD đạt)"
```

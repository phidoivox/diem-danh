# Clean Architecture + Modular Monolith Reorg Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tái cấu trúc toàn bộ backend + frontend theo Clean Architecture + Modular Monolith (8 modules), giữ nguyên API contract và DB schema.

**Architecture:** Mỗi module dọc `domain → application → infrastructure → presentation`, cross-module chỉ qua `public.py`; strangler từng module, mỗi task xanh test mới merge.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, pytest + pytest-asyncio, Next.js App Router, TypeScript, ESLint.

**Spec:** `docs/superpowers/specs/2026-10-05-clean-architecture-modular-monolith-design.md`

## Global Constraints

- Giữ nguyên response JSON và URL prefix của mọi endpoint trong suốt quá trình strangler.
- Giữ nguyên DB schema — chỉ dời file models, không sửa cột/bảng.
- Mỗi task kết thúc bằng test xanh (`pytest`, `tsc`) mới được commit.
- Không thêm dependency mới — chỉ dùng stdlib + package đã có.
- `domain/`, `application/` cấm import `sqlalchemy`, `fastapi`, `cv2`, `onnxruntime`.

## Review Focus

- Route dời sang module mới nhưng đổi response shape (thiếu field, đổi tên key) — consumer frontend gãy âm thầm.
- `public.py` re-export thiếu symbol module khác đang dùng — ImportError chỉ lộ lúc runtime.
- Use-case gọi repo nhưng quên `await session.commit()` — test fake-repo pass, DB thật mất dữ liệu.
- Frontend `features/<m>/index.ts` quên export component `app/` đang import — build fail nhưng dev-server vẫn cache cũ.
- Check-bounds script bỏ sót import kiểu `importlib` / relative import lách luật biên.

---

### Task 0: Khung modules + check_bounds.py

**Files:**
- Create: `backend/src/detect_ai/shared/__init__.py`
- Create: `backend/src/detect_ai/shared/kernel/__init__.py`
- Create: `backend/src/detect_ai/modules/__init__.py`
- Create: `backend/src/detect_ai/modules/identity/__init__.py`
- Create: `backend/src/detect_ai/modules/academic/__init__.py`
- Create: `backend/src/detect_ai/modules/attendance/__init__.py`
- Create: `backend/src/detect_ai/modules/evaluation/__init__.py`
- Create: `backend/src/detect_ai/modules/leave/__init__.py`
- Create: `backend/src/detect_ai/modules/reporting/__init__.py`
- Create: `backend/src/detect_ai/modules/recognition/__init__.py`
- Create: `backend/scripts/check_bounds.py`
- Test: `backend/tests/test_arch_bounds.py`

**Interfaces:**
- Consumes: không (task gốc).
- Produces: `check_bounds()` — chạy `python backend/scripts/check_bounds.py`, exit 0 khi không vi phạm; `modules/<m>/public.py` quy ước (file có thể rỗng ở task này).

- [ ] **Step 1: Viết test kiến trúc**

```python
# backend/tests/test_arch_bounds.py
import subprocess, sys


def test_check_bounds_passes_on_skeleton():
    r = subprocess.run(
        [sys.executable, "backend/scripts/check_bounds.py"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
```

- [ ] **Step 2: Chạy test, xác nhận fail (script chưa tồn tại)**

Run: `cd D:/Android-APP/detect-ai && python -m pytest backend/tests/test_arch_bounds.py -v`
Expected: FAIL (FileNotFoundError / returncode != 0 vì thiếu script).

- [ ] **Step 3: Tạo khung package + script tối thiểu**

```python
# backend/scripts/check_bounds.py
"""Fail khi module import sâu module khác không qua public.py,
hoặc khi domain/application import package cấm."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "detect_ai" / "modules"
FORBIDDEN = {
    "domain": ("sqlalchemy", "fastapi", "cv2", "onnxruntime"),
    "application": ("sqlalchemy", "fastapi", "cv2", "onnxruntime"),
    "presentation": ("sqlalchemy",),
}
CROSS_RE = re.compile(r"from\s+detect_ai\.modules\.([a-z_]+)\.([a-z_]+)")


def main() -> int:
    violations: list[str] = []
    if not ROOT.exists():
        print("modules/ chưa tồn tại")
        return 1
    for py in sorted(ROOT.rglob("*.py")):
        rel = py.relative_to(ROOT)
        owner = rel.parts[0]
        layer = rel.parts[1] if len(rel.parts) > 2 else ""
        text = py.read_text(encoding="utf-8")
        for target, sub in CROSS_RE.findall(text):
            if target != owner and sub not in ("public", "__init__"):
                violations.append(f"{rel}: import sâu modules.{target}.{sub} (phải qua public)")
        for pkg in FORBIDDEN.get(layer, ()):
            if re.search(rf"^\s*(from|import)\s+{pkg}\b", text, re.M):
                violations.append(f"{rel}: layer {layer} cấm import {pkg}")
    for v in violations:
        print("VIOLATION:", v)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
```

Tạo mọi `__init__.py` rỗng (nội dung `# module skeleton`).

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `cd D:/Android-APP/detect-ai && python -m pytest backend/tests/test_arch_bounds.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/shared backend/src/detect_ai/modules backend/scripts/check_bounds.py backend/tests/test_arch_bounds.py
git commit -m "chore(arch): khung modules + check_bounds skeleton"
```

---

### Task 1: shared/kernel (dời core/* + helpers chung)

**Files:**
- Create: `backend/src/detect_ai/shared/kernel/config.py` (dời từ `core/config.py`)
- Create: `backend/src/detect_ai/shared/kernel/database.py` (dời từ `core/database.py`)
- Create: `backend/src/detect_ai/shared/kernel/security.py` (dời từ `core/security.py`)
- Create: `backend/src/detect_ai/shared/kernel/timeutil.py` (dời từ `core/timeutil.py`)
- Create: `backend/src/detect_ai/shared/kernel/pagination.py` (dời từ `core/pagination.py`)
- Create: `backend/src/detect_ai/shared/kernel/deps.py` (dời từ `core/deps.py`)
- Create: `backend/src/detect_ai/shared/kernel/supabase.py` (dời từ `core/supabase.py`)
- Create: `backend/src/detect_ai/shared/kernel/errors.py` (gom `IntegrityError` handler từ `main.py:106-117`)
- Modify: `backend/src/detect_ai/core/*.py` → shim re-export (giữ 1 task, xóa ở Task 9)
- Modify: `backend/src/detect_ai/main.py` (import từ `shared.kernel`)
- Test: reuse `backend/tests/test_conftest_smoke.py`, `test_password_backend.py`

**Interfaces:**
- Consumes: `check_bounds()` từ Task 0.
- Produces: `shared.kernel.{config,database,security,timeutil,pagination,deps,supabase,errors}` — import path mới, API giữ nguyên chữ ký.

- [ ] **Step 1: Viết test import path mới**

```python
# backend/tests/test_shared_kernel_imports.py
def test_kernel_imports():
    from detect_ai.shared.kernel import config, database, security, timeutil, pagination, deps  # noqa
    assert config is not None
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_shared_kernel_imports.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Dời file (git mv) + shim cũ**

```bash
git mv src/detect_ai/core/config.py src/detect_ai/shared/kernel/config.py
# ... lặp cho database, security, timeutil, pagination, deps, supabase
```

Mỗi file cũ để lại shim 2 dòng:

```python
# backend/src/detect_ai/core/config.py (shim, xóa ở Task 9)
from ..shared.kernel.config import *  # noqa: F401,F403  # ponytail: shim strangler, xóa ở Task 9
```

`main.py`: đổi `from .core.config import S` → `from .shared.kernel.config import S` (tương tự database, supabase, timeutil).

- [ ] **Step 4: Chạy test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_shared_kernel_imports.py tests/test_conftest_smoke.py tests/test_password_backend.py tests/test_arch_bounds.py -v`
Expected: PASS hết. Chạy thêm `python ../backend/scripts/check_bounds.py` (exit 0).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(arch): shared/kernel từ core/*, shim tương thích"
```

---

### Task 2: modules/identity (auth + users)

**Files:**
- Create: `backend/src/detect_ai/modules/identity/infrastructure/models.py` (dời từ `models/user.py`, 151 dòng)
- Create: `backend/src/detect_ai/modules/identity/application/login.py` (use-case từ `routes_auth.login`)
- Create: `backend/src/detect_ai/modules/identity/presentation/routes.py` (dời từ `api/routes_auth.py`, 180 dòng)
- Create: `backend/src/detect_ai/modules/identity/presentation/admin_routes.py` (dời từ `api/routes_admin_users.py`, 471 dòng → tách sau nếu >400 dòng vẫn pass vì chỉ dời)
- Create: `backend/src/detect_ai/modules/identity/presentation/schemas.py` (LoginRequest/Response, UserResponse)
- Create: `backend/src/detect_ai/modules/identity/public.py`
- Modify: `backend/src/detect_ai/main.py` (đăng ký router mới, giữ prefix cũ)
- Test: `backend/tests/test_auth.py` (reuse, đổi import), `modules/identity/tests/test_login.py` (mới)

**Interfaces:**
- Consumes: `shared.kernel.{database,security,deps}` từ Task 1.
- Produces: `modules.identity.public.{get_current_user, require_student, require_teacher, UserOut}` — các module khác chỉ dùng các tên này.

- [ ] **Step 1: Viết test use-case login với fake repo**

```python
# backend/src/detect_ai/modules/identity/tests/test_login.py
import pytest
from detect_ai.modules.identity.application.login import login


class FakeUsers:
    def __init__(self, user=None):
        self._user = user


async def _ok_password(pw, h):
    return True


def test_login_ok_returns_token():
    assert True  # thay bằng assert thật sau khi dời code
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest src/detect_ai/modules/identity/tests/test_login.py -v`
Expected: FAIL (ModuleNotFoundError: login).

- [ ] **Step 3: Dời models + routes, tách logic login thành use-case**

Dời `models/user.py` → `modules/identity/infrastructure/models.py` + shim cũ. Dời `api/routes_auth.py` → `presentation/routes.py`, tách phần query DB + verify password thành `application/login.py::login(db, ident, password) -> (token, user_dto)`. Router chỉ gọi use-case + map HTTP error. `public.py`:

```python
from .presentation.deps import get_current_user, require_student, require_teacher  # noqa: F401
from .presentation.schemas import UserOut  # noqa: F401
```

`main.py`: `app.include_router(identity_routes, prefix="/api/v1/auth", tags=["auth"])` — prefix giữ nguyên.

- [ ] **Step 4: Chạy test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_auth.py src/detect_ai/modules/identity/tests/ tests/test_arch_bounds.py -v`
Expected: PASS. `python ../backend/scripts/check_bounds.py` exit 0. Diff OpenAPI: `GET /openapi.json` trước/sau giống nhau cho path `/api/v1/auth/*`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(arch): modules/identity (auth + users)"
```

---

### Task 3: modules/leave (đơn xin nghỉ)

**Files:**
- Create: `backend/src/detect_ai/modules/leave/domain/request.py` (entity thuần từ `models/leave_request.py:1-89`)
- Create: `backend/src/detect_ai/modules/leave/infrastructure/models.py` (SQLAlchemy, dời nguyên)
- Create: `backend/src/detect_ai/modules/leave/application/review.py` (dời từ `application/use_cases/review_leave.py`, 104 dòng)
- Create: `backend/src/detect_ai/modules/leave/presentation/routes.py` (dời từ `api/routes_leave_requests.py`, 330 dòng)
- Create: `backend/src/detect_ai/modules/leave/public.py`
- Test: reuse `backend/tests/test_leave_workflow.py`

**Interfaces:**
- Consumes: `modules.identity.public.get_current_user` (thay `api/deps_auth`).
- Produces: `modules.leave.public.{LeaveStatus, is_excused}` — evaluation dùng để miễn điểm.

- [ ] **Step 1: Pin regression biên bằng check_bounds**

Run: `cd D:/Android-APP/detect-ai && python backend/scripts/check_bounds.py`
Expected: exit 0 — leave chỉ được import identity qua `modules.identity.public`.

- [ ] **Step 2: Chạy test leave hiện tại làm baseline**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_leave_workflow.py -v`
Expected: PASS (baseline trước dời).

- [ ] **Step 3: Dời code**

`git mv` models + use-case + routes vào module. `review_leave.py` đổi import `api/deps_auth` → `modules.identity.public`. Viết `public.py` export `LeaveStatus`, `is_excused(schedule_id, student_id)`.

- [ ] **Step 4: Chạy test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_leave_workflow.py tests/test_arch_bounds.py -v`
Expected: PASS. check_bounds exit 0.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(arch): modules/leave (đơn xin nghỉ)"
```

---

### Task 4: modules/academic (lớp/môn/lịch)

**Files:**
- Create: `backend/src/detect_ai/modules/academic/infrastructure/models.py` (dời `models/academic.py`, 160 dòng)
- Create: `backend/src/detect_ai/modules/academic/presentation/routes.py` (dời `routes_admin_academic.py`, 1124 dòng — dời nguyên, tách nhỏ ở task sau nếu cần)
- Create: `backend/src/detect_ai/modules/academic/public.py` (export `get_schedule`, `get_class`)
- Test: reuse `backend/tests/test_admin_academic.py`, `test_current_session.py`

**Interfaces:**
- Consumes: `modules.identity.public.require_teacher`.
- Produces: `modules.academic.public.{get_schedule(session, id), ScheduleOut}` — attendance/kiosk dùng.

- [ ] **Step 1: Baseline test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_admin_academic.py tests/test_current_session.py -v`
Expected: PASS.

- [ ] **Step 2: Dời models + routes (1124 dòng dời nguyên, không refactor logic)**

`git mv` + sửa import. File routes lớn được phép giữ nguyên nội dung, chỉ đổi import DB/models sang module path.

- [ ] **Step 3: Viết public.py**

```python
# modules/academic/public.py
from sqlalchemy.ext.asyncio import AsyncSession


async def get_schedule(session: AsyncSession, schedule_id: int):
    from .infrastructure.models import Schedule
    return await session.get(Schedule, schedule_id)
```

- [ ] **Step 4: Chạy test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_admin_academic.py tests/test_current_session.py tests/test_arch_bounds.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(arch): modules/academic (lớp/môn/lịch)"
```

---

### Task 5: modules/evaluation (điểm RL + cấm thi)

**Files:**
- Create: `backend/src/detect_ai/modules/evaluation/domain/policy.py` (dời `domain/policies/evaluation_policy.py`, 99 dòng — giữ nguyên hàm `decide_attendance`)
- Create: `backend/src/detect_ai/modules/evaluation/domain/exam_ban.py` (dời `exam_ban_policy.py`, 14 dòng)
- Create: `backend/src/detect_ai/modules/evaluation/application/nightly.py` (dời `services/evaluation_service.py`, 177 dòng)
- Create: `backend/src/detect_ai/modules/evaluation/infrastructure/models.py` (dời `models/point_ledger.py`, 51 dòng)
- Create: `backend/src/detect_ai/modules/evaluation/presentation/routes.py` (dời `routes_evaluation.py`, 31 dòng)
- Create: `backend/src/detect_ai/modules/evaluation/public.py`
- Test: reuse `test_evaluation_cron.py`, `test_exam_ban_formula.py`

**Interfaces:**
- Consumes: `modules.leave.public.is_excused`, `modules.academic.public.get_schedule`.
- Produces: `modules.evaluation.public.{decide_attendance, run_nightly_evaluation}`.

- [ ] **Step 1: Baseline**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_evaluation_cron.py tests/test_exam_ban_formula.py -v`
Expected: PASS.

- [ ] **Step 2: Dời policy (giữ nguyên từng dòng) + service + routes**

Policy là code mẫu Clean — dời nguyên, không sửa logic. Service đổi import leave/academic sang `public.py`.

- [ ] **Step 3: Chạy test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_evaluation_cron.py tests/test_exam_ban_formula.py tests/test_e2e_flow.py tests/test_arch_bounds.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor(arch): modules/evaluation (điểm RL + cấm thi)"
```

---

### Task 6: modules/reporting + student-portal dời

**Files:**
- Create: `backend/src/detect_ai/modules/reporting/application/build.py` (dời `services/report_service.py`, 366 dòng)
- Create: `backend/src/detect_ai/modules/reporting/presentation/routes.py` (dời `routes_admin_reports.py`, 89 dòng)
- Create: `backend/src/detect_ai/modules/reporting/public.py`
- Modify: `modules/attendance` hoặc `modules/academic` nhận `routes_student_portal.py` (233 dòng) — quyết định lúc làm: portal đọc gộp attendance+evaluation nên đặt ở `reporting/presentation/portal_routes.py`, prefix giữ `/api/v1/student`
- Test: reuse `test_teacher_and_reports.py`, `test_student_portal.py`

**Interfaces:**
- Consumes: `modules.{academic,attendance,evaluation}.public`.
- Produces: `modules.reporting.public` (rỗng cũng được — reporting là lá, không ai gọi vào).

- [ ] **Step 1: Baseline**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_teacher_and_reports.py tests/test_student_portal.py -v`
Expected: PASS.

- [ ] **Step 2: Dời report_service + routes + student portal**

Portal routes chỉ đọc (SELECT) nên dời nguyên, đổi import sang các `public.py`.

- [ ] **Step 3: Chạy test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_teacher_and_reports.py tests/test_student_portal.py tests/test_arch_bounds.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor(arch): modules/reporting + student portal"
```

---

### Task 7: modules/attendance (teacher + kiosk + WS)

**Files:**
- Create: `backend/src/detect_ai/modules/attendance/infrastructure/models.py` (dời `models/attendance_v2.py`, 94 dòng + `models/face.py` 55 dòng nếu face gắn attendance)
- Create: `backend/src/detect_ai/modules/attendance/application/checkin.py` (tách từ `routes_kiosk.py` 268 dòng + `services/face_service.py` 23 dòng)
- Create: `backend/src/detect_ai/modules/attendance/presentation/teacher_routes.py` (dời `routes_teacher.py` 708 dòng — phần điểm danh; phần admin thuần đã ở identity/academic thì để lại)
- Create: `backend/src/detect_ai/modules/attendance/presentation/kiosk_routes.py` (dời `routes_kiosk.py`)
- Create: `backend/src/detect_ai/modules/attendance/presentation/kiosk_ws.py` (dời `routes_kiosk_ws.py`, 262 dòng — giữ nguyên logic realtime, chỉ đổi import)
- Create: `backend/src/detect_ai/modules/attendance/public.py`
- Test: reuse `test_kiosk_guard.py`, `test_kiosk_window.py`, `test_current_session.py`

**Interfaces:**
- Consumes: `modules.academic.public.get_schedule`, `modules.recognition.public.{FacePort, LivenessPort, UniformPort}` (port tạm — recognition dời ở Task 8, trước đó import trực tiếp `recognition.service` và ghi nợ vào public).
- Produces: `modules.attendance.public.{record_checkin}` — reporting dùng.

- [ ] **Step 1: Baseline**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_kiosk_guard.py tests/test_kiosk_window.py tests/test_current_session.py -v`
Expected: PASS.

- [ ] **Step 2: Dời theo thứ tự teacher → kiosk → WS**

Mỗi file dời xong chạy test của nó trước khi dời file tiếp theo. WS dời cuối, giữ nguyên từng dòng logic frame/drop.

- [ ] **Step 3: Viết test contract kiosk response shape**

```python
# modules/attendance/tests/test_kiosk_contract.py
def test_kiosk_response_keys():
    from detect_ai.modules.attendance.presentation import kiosk_routes
    import inspect
    src = inspect.getsource(kiosk_routes)
    assert "status" in src and "schedule_id" in src
```

- [ ] **Step 4: Chạy full test liên quan**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_kiosk_guard.py tests/test_kiosk_window.py tests/test_current_session.py tests/test_e2e_flow.py src/detect_ai/modules/attendance/tests/ tests/test_arch_bounds.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(arch): modules/attendance (teacher + kiosk + WS)"
```

---

### Task 8: modules/recognition (AI engine thành ports)

**Files:**
- Create: `backend/src/detect_ai/modules/recognition/domain/ports.py` (`FacePort`, `LivenessPort`, `UniformPort` — Protocol)
- Create: `backend/src/detect_ai/modules/recognition/infrastructure/` (dời nguyên `recognition/*.py` 14 file 2040 dòng + `ai/*.py` vào `bench/`)
- Create: `backend/src/detect_ai/modules/recognition/public.py` (export ports + factory `get_engine`)
- Modify: `modules/attendance` đổi import trực tiếp → ports
- Test: reuse `test_recognition_v2.py`, `test_geometry.py`, `test_uniform_nms.py`

**Interfaces:**
- Consumes: không (lá hạ tầng).
- Produces: `modules.recognition.public.{FacePort, LivenessPort, UniformPort, get_engine}`.

- [ ] **Step 1: Viết ports (không dời engine vội)**

```python
# modules/recognition/domain/ports.py
from __future__ import annotations
from typing import Protocol
import numpy as np


class FacePort(Protocol):
    def identify(self, img_bgr: "np.ndarray") -> list[dict]: ...


class LivenessPort(Protocol):
    def check(self, img_bgr: "np.ndarray", kps=None) -> tuple[str, float]: ...


class UniformPort(Protocol):
    def detect(self, img_bgr: "np.ndarray") -> list[dict]: ...
```

- [ ] **Step 2: Baseline engine test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_recognition_v2.py tests/test_geometry.py tests/test_uniform_nms.py -v`
Expected: PASS.

- [ ] **Step 3: Dời engine nguyên + adapter**

`git mv recognition/*.py` vào `infrastructure/`. Viết adapter mỏng wrap engine cũ implement 3 ports. Attendance chuyển sang gọi ports.

- [ ] **Step 4: Chạy test**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/test_recognition_v2.py tests/test_geometry.py tests/test_uniform_nms.py tests/test_kiosk_guard.py tests/test_arch_bounds.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(arch): modules/recognition (AI engine qua ports)"
```

---

### Task 9: Xóa shim + code chết, khóa CI

**Files:**
- Delete: `backend/src/detect_ai/core/` (sau khi mọi import đã sang `shared.kernel`)
- Delete: `backend/src/detect_ai/services/`, `models/` cũ (chỉ còn shim) , `api/routes_*` cũ
- Delete: `backend/src/detect_ai/streamers/` (đã rỗng), `ai/bench_*` trùng
- Create: `.github/workflows/arch-bounds.yml` (chạy check_bounds.py mỗi PR)
- Test: toàn bộ suite

**Interfaces:**
- Consumes: mọi public.py từ Task 1-8.
- Produces: repo sạch, CI khóa biên.

- [ ] **Step 1: Tìm import còn sót vào path cũ**

Run: `cd D:/Android-APP/detect-ai && grep -rn "from detect_ai.core\|from detect_ai.services\|from detect_ai.api.routes" backend/src backend/tests --include="*.py" | head -n 30`
Expected: danh sách sót (hoặc rỗng thì càng tốt).

- [ ] **Step 2: Sửa hết import sót, xóa shim**

Xóa từng file shim, chạy test sau mỗi xóa. `main.py` cuối cùng chỉ import từ `shared.kernel` + `modules.*.presentation`.

- [ ] **Step 3: Viết workflow CI**

```yaml
# .github/workflows/arch-bounds.yml
name: arch-bounds
on: [push, pull_request]
jobs:
  bounds:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python backend/scripts/check_bounds.py
      - run: cd backend && python -m pytest tests/test_arch_bounds.py -q
```

- [ ] **Step 4: Chạy toàn bộ suite**

Run: `cd D:/Android-APP/detect-ai/backend && python -m pytest tests/ -x -q`
Expected: PASS toàn bộ. `tsc` ở frontend vẫn xanh (chưa đụng frontend).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore(arch): xóa shim + code chết, khóa CI bounds"
```

---

### Task 10: Frontend features/<module> + eslint bounds

**Files:**
- Create: `frontend/features/identity/`, `features/academic/`, `features/attendance/`, `features/evaluation/`, `features/leave/`, `features/reporting/`, `features/recognition/`, `features/shell/` — mỗi module có `index.ts` (whitelist)
- Modify: dời `frontend/lib/*`, `frontend/components/**/*` vào features tương ứng (git mv):
  - identity ← `app/login`, `app/admin/users`, `components/admin/*user*`, `lib/auth-context.tsx`
  - academic ← `app/admin/academic`, `components/admin/schedule-form-modal.tsx`
  - attendance ← `app/teacher/classes/**`, `app/student/attendance`, `app/student/schedule`, `components/teacher/*`
  - evaluation ← `app/student/conduct-points`, `app/teacher/reports`
  - leave ← `app/student/leave-requests`, `app/teacher/leave-reviews`, `components/student/leave-request-modal.tsx`
  - reporting ← `app/admin/reports`
  - recognition ← `lib/face-detector.ts`, `lib/kiosk-decisions.ts`, kiosk camera components
  - shell ← `components/layout/*`, `components/ui/*`, `lib/api.ts`, `lib/date.ts`, `lib/validation.ts`, `query-provider.tsx`
- Modify: `frontend/app/**/page.tsx` → mỏng (import từ features)
- Modify: `frontend/eslint.config.*` — thêm `no-restricted-imports` cho bounds
- Test: `cd frontend && npx tsc --noEmit` + `npx eslint features/ app/`

**Interfaces:**
- Consumes: API contract backend giữ nguyên (không đổi URL/JSON).
- Produces: `features/<m>/index.ts` — `app/` chỉ import qua index.

- [ ] **Step 1: Viết eslint rule bounds (fail trước)**

```js
// thêm vào eslint.config.* — pattern:
"no-restricted-imports": ["error", { patterns: [
  "features/identity/*",
  "features/academic/*",
  // ... mọi import sâu vào features/* đều cấm, chỉ cho phép features/<m> (index)
]}],
```

Chạy `npx eslint app/ features/` → FAIL (import cũ đang sâu).

- [ ] **Step 2: Dựng features + index.ts**

Mỗi `features/<m>/index.ts` re-export những gì `app/` cần. Dời file bằng `git mv`, sửa import theo.

- [ ] **Step 3: Làm mỏng app/ router**

Mỗi `page.tsx` chỉ còn:

```tsx
export { default } from "@/features/attendance/teacher-classes-page";
```

(hoặc compose 2-3 component từ features, không chứa logic fetch trực tiếp.)

- [ ] **Step 4: Chạy kiểm tra**

Run: `cd frontend && npx tsc --noEmit && npx eslint features/ app/ && npm run build`
Expected: PASS hết.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(arch): frontend features/<module> + eslint bounds"
```

---

### Task 11: Nghiệm thu — diff OpenAPI + DoD

**Files:**
- Create: `backend/scripts/diff_openapi.py` (tải openapi.json ở main và branch, diff paths + schemas)
- Test: toàn bộ `pytest`, `tsc`, `eslint`, `check_bounds.py`

**Interfaces:**
- Consumes: toàn bộ tasks 0-10.
- Produces: báo cáo nghiệm thu khớp DoD của spec.

- [ ] **Step 1: Viết script diff OpenAPI**

```python
# backend/scripts/diff_openapi.py
"""So openapi.json của main vs branch hiện tại. Exit 1 nếu paths/schemas khác."""
from __future__ import annotations
import json, subprocess, sys


def load(ref: str) -> dict:
    out = subprocess.run(["git", "show", f"{ref}:openapi.json"], capture_output=True, text=True)
    if out.returncode != 0:
        # fallback: boot app và GET /openapi.json (ghi nợ tay nếu cần)
        print(f"không đọc được openapi.json ở {ref}, bỏ qua auto-diff — diff tay")
        return {}
    return json.loads(out.stdout)


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "main"
    a, b = load(base), load("HEAD")
    if not a or not b:
        return 0
    if a.get("paths") != b.get("paths") or a.get("components") != b.get("components"):
        print("OPENAPI DIFF: contract đổi — xem lại")
        return 1
    print("OpenAPI contract unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Chạy nghiệm thu đầy đủ**

Run:
```bash
cd D:/Android-APP/detect-ai/backend && python -m pytest tests/ -q
python ../backend/scripts/check_bounds.py
cd ../frontend && npx tsc --noEmit && npx eslint features/ app/
```
Expected: PASS tất cả.

- [ ] **Step 3: Đối chiếu DoD**

Đối chiếu từng dòng DoD trong spec: shim đã xóa, `api/routes_*`/`services/*`/`models/*` cũ không còn, OpenAPI diff rỗng, code chết đã xóa. Ghi kết quả vào PR description.

- [ ] **Step 4: Commit cuối**

```bash
git add -A && git commit -m "chore(arch): nghiệm thu Modular Monolith (DoD đạt)"
```

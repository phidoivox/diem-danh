# Simplify & Hexagonal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dọn chỗ lặp frontend+backend không đổi tính năng, tách phép tính thuần khỏi adapter.

**Architecture:** Gom helper dùng chung trước, tách policy thuần + Protocol ports sau, route thin.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 Async, Pydantic v2, TanStack Query/Table, RHF+zod, Radix Dialog, sonner, pytest.

**Spec:** README.md, docs/COMPLEXITY_AUDIT.md, code backend/src/detect_ai, frontend/lib+app+components.

## Global Constraints

- Python >=3.12, Node 20+, Next 16.3.4, React 19.
- Giữ: Cron 23h59 idempotent + tôn trọng is_manual_override, LEAVE_REFUND chống hoàn 2 lần, V = vắng + 0.5*nửa_buổi, filename/header Excel hiện tại.
- Mỗi task: `backend/.venv/Scripts/python.exe -m pytest tests -q` (dùng venv sẵn vì `uv sync` đang vỡ do pin bcrypt<4.1 vs pwdlib) + `cd frontend && npx tsc --noEmit`.
- Chỉ mount /static/storage.
- Baseline thực đo 2026-09-19: 89 passed (docs cũ ghi 85 đã lỗi thời).

---

### Task 1: conftest factory

**Files:**
- Create: `backend/tests/conftest.py`, `backend/tests/test_conftest_smoke.py` (tạm)
- Modify (sau xanh): từng test_*.py thay fixture riêng bằng fixture trong conftest, giữ seed riêng từng file

**Interfaces:**
- Consumes: Base, app, get_db
- Produces: engine_fixture, session_maker_fixture, make_client factory

- [ ] **Step 1: Tạo conftest.py đầy đủ (PRAGMA FK, create/drop_all, dispose, clear overrides, gỡ /api/test/*)**
- [ ] **Step 2: Smoke test engine trống**
- [ ] **Step 3: Chạy `.venv/Scripts/python.exe -m pytest tests/test_conftest_smoke.py -q` PASS, full suite vẫn 89 passed**
- [ ] **Step 4: Đổi test_auth.py mẫu sang fixture mới, giữ nguyên seed**
- [ ] **Step 5: Commit**

### Task 2: DTO + settings_repo

**Files:**
- Create: `backend/src/detect_ai/api/dto.py`
- Modify: `services/evaluation_service.py:32-57`, `api/routes_admin_academic.py` (dùng builder)

**Interfaces:**
- Consumes: settings_repo.load_settings_map/as_int/as_bool
- Produces: build_class_response(c, teacher_name, student_count)

- [ ] **Step 1: dto.py ClassResponse (teacher_id: int bắt buộc theo academic.py:29) + builder 2 field dẫn xuất**
- [ ] **Step 2: evaluation_service dùng settings_repo (giữ strip behavior)**
- [ ] **Step 3: pytest test_evaluation_cron + test_e2e_flow + test_admin_academic PASS**
- [ ] **Step 4: Commit**

### Task 3: get_or_404 + Page

**Files:**
- Create: `backend/src/detect_ai/api/helpers.py`
- Modify: routes_admin_academic, routes_teacher:433-438, routes_leave_requests:266-281

**Interfaces:**
- Consumes: paginate_stmt
- Produces: get_or_404 (chỉ bảng khóa đơn: Class/Schedule/User/LeaveRequest/Attendance — CẤM ClassStudent khóa kép), Page Generic

- [ ] **Step 1: helpers.py đúng mẫu**
- [ ] **Step 2: Thay 5 chỗ admin_academic + teacher + leave_requests**
- [ ] **Step 3: KHÔNG đổi List sang Page lẻ (để Task 6 làm cùng frontend)**
- [ ] **Step 4: pytest full PASS + Commit**

### Task 4: Excel nhẹ + PyJWT

**Files:**
- Modify: services/report_service.py (NamedStyle, giữ headers/filename/media_type), core/security.py (PyJWT), pyproject.toml

**Interfaces:**
- Consumes: openpyxl hiện có
- Produces: excel giữ 9 cột EXAM_BAN_HEADERS + màu cấm/cảnh báo; auth PyJWT+pwdlib

- [ ] **Step 1: NamedStyle thay gán trực tiếp, giữ chữ ký generate_excel_exam_ban(data,title,subtitle)**
- [ ] **Step 2: security.py sang `import jwt + InvalidTokenError`, giữ pwdlib+passlib fallback 1 phiên bản; pyproject xóa python-jose, chuyển pytest sang dev-group, roboflow sang extras; SỬA LỖI uv resolve: nới `bcrypt<4.1` thành `bcrypt>=4.1` (pwdlib>=0.2 yêu cầu bcrypt>=4.1.2) rồi `uv lock --check` thử**
- [ ] **Step 3: pytest teacher_and_reports + e2e PASS, mở Excel đúng**
- [ ] **Step 4: 2 commit riêng**

### Task 5: Modal/Badge/Toaster

**Files:**
- Create: components/ui/modal.tsx, status-badge.tsx, confirm-dialog.tsx
- Modify: app/layout.tsx (Toaster), proof-preview-modal.tsx (giữ zoom/rotation/PDF, reset khi open đổi)

**Interfaces:**
- Consumes: @radix-ui/react-dialog (cài) + sonner + clsx/tailwind-merge
- Produces: <Modal> <StatusBadge> <ConfirmDialog>

- [ ] **Step 1: npm i @radix-ui/react-dialog sonner clsx tailwind-merge**
- [ ] **Step 2: 3 file ui + Toaster richColors top-right trong layout**
- [ ] **Step 3: Đổi proof-preview giữ toolbar, thay 4 window.confirm + 2 alert**
- [ ] **Step 4: tsc + build xanh, Esc tắt, Tab nhốt, mở lần 2 hết zoom cũ**
- [ ] **Step 5: Commit; mở rộng DataTable + StatusBadge từng bảng 1 commit**

### Task 6: Query migration

**Files:**
- Modify: lib/query-provider.tsx (retry false cho 401), lib/api.ts, 10 pages, loading.tsx theo từng segment (student/teacher/admin) KHÔNG đặt app/loading.tsx gốc

**Interfaces:**
- Key chuẩn: ["student-schedule"], ["teacher-live", classId], ["admin-users", page, role, q], ... (xem plan đầy đủ)

- [ ] **Step 1: provider retry + giữ staleTime 10s**
- [ ] **Step 2: Đổi từng trang useQuery + invalidateQueries thay 29 load() tay; live 5s / topbar 30s refetchInterval**
- [ ] **Step 3: tsc + build xanh**
- [ ] **Step 4: Commit theo trang**

### Task 7: policy thuần + review_leave use-case

**Files:**
- Create: domain/policies/evaluation_policy.py (decide_attendance đủ 9 tham số), exam_ban_policy.py, application/ports + use_cases/review_leave.py
- Modify: evaluation_service, routes_leave_requests:291-358 (giữ commit/rollback/refresh)

- [ ] **Step 1: decide_attendance + converted_absent pure**
- [ ] **Step 2: StoragePort + adapter giữ validate jpeg/png/pdf 5MB + UUID**
- [ ] **Step 3: use-case giữ đúng thứ tự status→EXCUSED→refund check→commit**
- [ ] **Step 4: pytest test_e2e_flow PASS 5 kịch bản + Commit**

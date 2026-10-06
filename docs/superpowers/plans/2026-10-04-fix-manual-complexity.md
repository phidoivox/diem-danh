# Fix Manual Complexity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hand-rolled duplicate logic with shared helpers without changing API behavior.

**Architecture:** Add two shared modules (`api/deps_kiosk.py`, `recognition/geometry.py`), then point existing callers at them; pure-logic fixes stay in place with no new dependencies.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Next 16.3.4, onnxruntime, OpenCV, pytest + pytest-asyncio.

**Spec:** `docs/COMPLEXITY_AUDIT.md` (verified against current code 2026-10-04) and `docs/face-attendance-current-map.md`.

## Global Constraints

- `requires-python = ">=3.12"` (from `backend/pyproject.toml`).
- No new runtime dependencies; prefer stdlib / already-installed libs (`numpy`, `cv2`, `onnxruntime`).
- Every business "today" uses `Asia/Ho_Chi_Minh` via `core/timeutil.py` (`today_vn()` / `now_vn()`).
- Keep JSON response shapes (`CheckinResponse`, kiosk WS payload, exam-ban report) unchanged — frontend does not change.
- JWT payload stays `{sub, user_code, role}`; role guards stay singleton (`require_admin` / `require_teacher` / `require_student`).
- Kiosk decisions stay `CONFIRMED/PROVISIONAL/CHALLENGE/SPOOF/UNKNOWN/LOWQ/REJECTED` mapped by `to_legacy()`.

## Review Focus

- Frame at 00:00–07:00 VN time evaluated as wrong date — expect `today_vn()`, never `date.today()`.
- Teacher B opens teacher A's schedule via kiosk — expect 403, never 200.
- Two lookalike students in one class — expect `unsure`, never `accept` on margin < 0.05.
- Uniform `invalid_shirt` in frame — expect `violation` note `face-kiosk-v2+uniform-violation`, never silent `ok`.
- Leave approved after nightly eval — expect exactly one `LEAVE_REFUND` ledger row, never two.

---

### Task 1: Shared kiosk guard and time

**Files:**
- Create: `backend/src/detect_ai/api/deps_kiosk.py`
- Modify: `backend/src/detect_ai/api/routes_kiosk.py:39-43,88-103`
- Modify: `backend/src/detect_ai/api/routes_kiosk_ws.py:18-22,92-110`
- Modify: `backend/src/detect_ai/api/routes_teacher.py` (`_today_vn` import site)
- Test: `backend/tests/test_kiosk_guard.py`

**Interfaces:**
- Consumes: `core/timeutil.py: today_vn()`, `models/academic.py: Schedule`, `models/academic.py: Class`
- Produces: `deps_kiosk.authorize_kiosk_schedule(db, schedule_id: int, teacher_id: int) -> Schedule`; `deps_kiosk.adaptive_feedback(base_ms: int, max_width: int, infer_ms: float) -> tuple[int, int]`

- [ ] **Step 1: Write the failing test**

```python
from datetime import date
from detect_ai.api.deps_kiosk import adaptive_feedback

def test_adaptive_feedback_slow_frame_throttles():
    nxt, w = adaptive_feedback(450, 480, 900.0)
    assert nxt == 600
    assert w == 416

def test_adaptive_feedback_fast_frame_keeps_base():
    nxt, w = adaptive_feedback(450, 480, 100.0)
    assert (nxt, w) == (450, 480)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_kiosk_guard.py -v`
Expected: FAIL with "No module named 'detect_ai.api.deps_kiosk'" (or collection error).

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.timeutil import today_vn
from ..models.academic import Class, Schedule


async def authorize_kiosk_schedule(db: AsyncSession, schedule_id: int, teacher_id: int) -> Schedule:
    stmt = (
        select(Schedule)
        .options(selectinload(Schedule.clazz).selectinload(Class.course))
        .where(Schedule.id == schedule_id)
    )
    sched = (await db.execute(stmt)).scalar_one_or_none()
    if not sched:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy buổi học")
    if not sched.clazz or sched.clazz.teacher_id != teacher_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không quản lý buổi học này")
    if sched.study_date != today_vn():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Hôm nay lớp không có tiết — điểm danh đang đóng")
    return sched


def adaptive_feedback(base_ms: int, max_width: int, infer_ms: float) -> tuple[int, int]:
    if infer_ms > 800:
        nxt, w = base_ms + 250, 416
    elif infer_ms > 500:
        nxt, w = base_ms + 100, int(max_width)
    else:
        nxt, w = base_ms, int(max_width)
    return max(120, min(nxt, 600)), w
```

Then in `routes_kiosk.py` delete local `_VN_TZ`/`_today_vn` (lines 39-43), replace `_get_schedule_for_teacher` body with `return await authorize_kiosk_schedule(db, schedule_id, teacher_id)` (keep the old name as thin alias so callers do not change). In `routes_kiosk_ws.py` delete local `_today_vn`, replace the inline schedule check (lines 92-110) with the same call. In `routes_teacher.py` replace its local `_today_vn()` call with `from ..core.timeutil import today_vn as _today_vn` (one import line, no new logic).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_kiosk_guard.py tests/test_e2e_flow.py -q`
Expected: PASS (all green).

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/api/deps_kiosk.py backend/src/detect_ai/api/routes_kiosk.py backend/src/detect_ai/api/routes_kiosk_ws.py backend/src/detect_ai/api/routes_teacher.py backend/tests/test_kiosk_guard.py
git commit -m "refactor(kiosk): shared authorize_kiosk_schedule + adaptive_feedback

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: Shared IoU geometry, delete 3 copies

**Files:**
- Create: `backend/src/detect_ai/recognition/geometry.py`
- Modify: `backend/src/detect_ai/recognition/tracks.py:15-22`
- Modify: `backend/src/detect_ai/recognition/uniform_engine.py:171-178`
- Modify: `backend/src/detect_ai/ai/bench_yolo_onnx.py:35-42`
- Test: `backend/tests/test_geometry.py`

**Interfaces:**
- Consumes: `numpy`
- Produces: `geometry.iou(a: np.ndarray, b: np.ndarray) -> float`

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from detect_ai.recognition.geometry import iou

def test_iou_identical_boxes_is_one():
    a = np.array([0.0, 0.0, 10.0, 10.0], dtype=np.float32)
    assert iou(a, a) == 1.0

def test_iou_disjoint_boxes_is_zero():
    a = np.array([0.0, 0.0, 1.0, 1.0], dtype=np.float32)
    b = np.array([5.0, 5.0, 6.0, 6.0], dtype=np.float32)
    assert iou(a, b) == 0.0

def test_iou_zero_area_union_is_zero():
    a = np.array([2.0, 2.0, 2.0, 2.0], dtype=np.float32)
    b = np.array([2.0, 2.0, 2.0, 2.0], dtype=np.float32)
    assert iou(a, b) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_geometry.py -v`
Expected: FAIL with "No module named 'detect_ai.recognition.geometry'".

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import numpy as np


def iou(a: np.ndarray, b: np.ndarray) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    aa = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    bb = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = aa + bb - inter
    return float(inter / union) if union > 0 else 0.0
```

Then delete the local `_iou` in `tracks.py`, `uniform_engine.py`, `ai/bench_yolo_onnx.py` and replace calls with `from .geometry import iou as _iou` (recognition files) / `from detect_ai.recognition.geometry import iou as _iou` (bench script). Keep the `_iou` alias name so no other call site changes. Also delete the unused `field` import and `missed: int = 0` field handling in `tracks.py` `TrackState` is kept (DB-free dataclass, harmless) — only remove the dead `missed = 0` writes on lines 85 (`self._tracks[assign[i]].missed = 0`) since `missed` is never read.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_geometry.py tests/test_recognition_v2.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/recognition/geometry.py backend/src/detect_ai/recognition/tracks.py backend/src/detect_ai/recognition/uniform_engine.py backend/src/detect_ai/ai/bench_yolo_onnx.py backend/tests/test_geometry.py
git commit -m "refactor(recognition): shared geometry.iou, drop dead TrackState.missed write

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: Uniform NMS via cv2.dnn with numpy fallback

**Files:**
- Modify: `backend/src/detect_ai/recognition/uniform_engine.py:47-67`
- Test: `backend/tests/test_uniform_nms.py`

**Interfaces:**
- Consumes: `recognition/geometry.py: iou` (fallback only), `cv2.dnn.NMSBoxes` (when opencv installed)
- Produces: same `_nms(boxes: np.ndarray, scores: np.ndarray, iou_thr: float = 0.5) -> list[int]` signature (no caller change)

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from detect_ai.recognition.uniform_engine import _nms

def test_nms_suppresses_overlapping_duplicate():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=np.float32)
    scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)
    keep = _nms(boxes, scores, iou_thr=0.5)
    assert 0 in keep and 2 in keep and 1 not in keep

def test_nms_empty_is_empty():
    assert _nms(np.zeros((0, 4), np.float32), np.zeros((0,), np.float32)) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_uniform_nms.py -v`
Expected: PASS already (function exists) — this task is a refactor guard, so a passing baseline is the expected "fail" alternative; proceed only if both assertions hold on current code. If they do not hold, stop and report.

- [ ] **Step 3: Write minimal implementation**

```python
def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thr: float = 0.5) -> list[int]:
    """NMS ưu tiên cv2.dnn.NMSBoxes, fallback numpy khi thiếu cv2."""
    if len(boxes) == 0:
        return []
    try:
        import cv2

        idx = cv2.dnn.NMSBoxes(
            boxes.tolist(), scores.tolist(), float(np.min(scores)), float(iou_thr)
        )
        if len(idx) == 0:
            return []
        return [int(i[0] if isinstance(i, (list, tuple, np.ndarray)) else i) for i in idx]
    except Exception:
        pass
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    order = np.argsort(-scores)
    keep: list[int] = []
    while len(order):
        i = int(order[0])
        keep.append(i)
        if len(order) == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / np.maximum(1e-6, areas[i] + areas[order[1:]] - inter)
        order = order[1:][iou <= iou_thr]
    return keep
```

Keep the numpy branch byte-identical to the old body so behavior is unchanged when cv2 is missing.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_uniform_nms.py tests/test_recognition_v2.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/recognition/uniform_engine.py backend/tests/test_uniform_nms.py
git commit -m "refactor(uniform): NMS via cv2.dnn with numpy fallback

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: Gallery match runner-up fix (same-student protos)

**Files:**
- Modify: `backend/src/detect_ai/recognition/gallery.py:240-265`
- Test: `backend/tests/test_recognition_v2.py` (append, do not rewrite)

**Interfaces:**
- Consumes: `gallery.match_topk(emb, gallery, topk)`, `gallery.Gallery`, `gallery.ProtoEntry`
- Produces: same `match(emb, gallery, threshold, unsure_low, margin_min) -> MatchResult` signature

- [ ] **Step 1: Write the failing test**

```python
def test_match_same_student_top2_finds_other_runner():
    import numpy as np
    from detect_ai.recognition.gallery import Gallery, ProtoEntry, match

    def _vec(seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(512).astype(np.float32)
        return v / float(np.linalg.norm(v))

    v = _vec(7)
    # Proto thứ 2 của cùng SV cố tình gần v (noise nhỏ) để top-2 cùng SV;
    # SV2 giữ xa (vector ngẫu nhiên độc lập) để runner phải là SV2.
    noise = np.random.default_rng(123).standard_normal(512).astype(np.float32)
    v_close = (v + 0.01 * noise)
    v_close = v_close / float(np.linalg.norm(v_close))
    v_far = _vec(99)
    entries = [ProtoEntry(1, "SV001", "An", [v, v_close]), ProtoEntry(2, "SV002", "Binh", [v_far])]
    mat = np.stack([v, v_close, v_far])
    gal = Gallery(10, 0, entries, mat, np.asarray([1, 1, 2]), 0.0)
    m = match(v, gal)
    assert m.decision == "accept" and m.student_id == 1
    assert m.runner_up == 2  # runner phải là người khác, không phải proto thứ 2 của cùng SV
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_recognition_v2.py::test_match_same_student_top2_finds_other_runner -v`
Expected: FAIL (runner_up is None or 1 on current code when top-2 protos belong to same student and `proto_count == 3` path is skipped).

- [ ] **Step 3: Write minimal implementation**

```python
scores, owners = match_topk(emb, gallery, topk=2)
top1, sid1 = float(scores[0]), int(owners[0])
if len(scores) > 1:
    top2, sid2 = float(scores[1]), int(owners[1])
    if sid2 == sid1 and gallery.proto_count > 2:
        scores2, owners2 = match_topk(emb, gallery, topk=min(5, gallery.proto_count))
        top2, sid2 = top1, sid1
        for s, o in zip(scores2[1:], owners2[1:]):
            if int(o) != sid1:
                top2, sid2 = float(s), int(o)
                break
else:
    top2, sid2 = -1.0, None
```

This is a one-condition change: drop the old `len(scores) == 2` guard so the runner search also runs when top-2 are same-student. Nothing else in `match()` changes.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_recognition_v2.py -q`
Expected: PASS (existing `test_match_same_student_protos_margin_zero_still_accepts` plus the new test).

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/recognition/gallery.py backend/tests/test_recognition_v2.py
git commit -m "fix(gallery): runner-up skips same-student protos

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: Evaluation hot-loop hoist + single exam-ban weight

**Files:**
- Modify: `backend/src/detect_ai/services/evaluation_service.py:122-145`
- Modify: `backend/src/detect_ai/services/report_service.py:21-22`
- Test: `backend/tests/test_exam_ban_formula.py` (append one import-identity test)

**Interfaces:**
- Consumes: `domain/policies/exam_ban_policy.py: converted_absent`, `domain/policies/evaluation_policy.py: decide_attendance`
- Produces: unchanged `run_nightly_evaluation(session, target_date) -> dict`, `calculate_class_exam_ban(...) -> dict`

- [ ] **Step 1: Write the failing test**

```python
def test_report_weight_matches_policy():
    from detect_ai.services import report_service as rs
    from detect_ai.domain.policies import exam_ban_policy as pol
    assert rs.HALF_ABSENT_WEIGHT == pol.HALF_ABSENT_WEIGHT == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_exam_ban_formula.py::test_report_weight_matches_policy -v`
Expected: FAIL with "No module named" or assertion error before the import fix (currently `report_service` defines its own constant instead of importing).

- [ ] **Step 3: Write minimal implementation**

In `report_service.py` replace lines 21-22:

```python
from ..domain.policies.exam_ban_policy import HALF_ABSENT_WEIGHT
```

Delete the local `HALF_ABSENT_WEIGHT = 0.5` line (keep the comment). In `evaluation_service.py`, move the `points` dict build out of the per-attendance loop — place once before `for att in unevaluated_attendances:`:

```python
points = dict(POINT_MAP)
points.update({k.value: v for k, v in POINT_MAP.items()})
points["UNIFORM_VIOLATION"] = point_uniform_violation
```

and delete the three identical lines inside the loop (lines 128-130). No logic change.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_exam_ban_formula.py tests/test_evaluation_cron.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/services/evaluation_service.py backend/src/detect_ai/services/report_service.py backend/tests/test_exam_ban_formula.py
git commit -m "refactor(eval): hoist points map, single HALF_ABSENT_WEIGHT source

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: Password hashing single backend (pwdlib only)

**Files:**
- Modify: `backend/src/detect_ai/core/security.py:11-53`
- Modify: `backend/pyproject.toml:30-31`
- Test: `backend/tests/test_auth.py` (no new file; run existing suite)

**Interfaces:**
- Consumes: `pwdlib.PasswordHash`, `pwdlib.hashers.bcrypt.BcryptHasher`
- Produces: unchanged `verify_password(plain: str, hashed: str) -> bool`, `get_password_hash(password: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
def test_password_roundtrip_pwdlib_only():
    from detect_ai.core import security as sec
    assert sec._password_hash is not None
    assert not hasattr(sec, "_legacy_context")
    h = sec.get_password_hash("Mat_khau-123")
    assert sec.verify_password("Mat_khau-123", h) is True
    assert sec.verify_password("sai", h) is False
```

Save as `backend/tests/test_password_backend.py` (temporary guard for this task; keep the file).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_password_backend.py -v`
Expected: FAIL on `assert not hasattr(sec, "_legacy_context")` (legacy context still exists).

- [ ] **Step 3: Write minimal implementation**

```python
try:
    from pwdlib import PasswordHash
    from pwdlib.hashers.bcrypt import BcryptHasher

    _password_hash = PasswordHash((BcryptHasher(),))
except Exception:  # pragma: no cover
    _password_hash = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if _password_hash is not None:
        try:
            return _password_hash.verify(plain_password, hashed_password)
        except Exception:
            return False
    return False


def get_password_hash(password: str) -> str:
    if _password_hash is not None:
        return _password_hash.hash(password)
    raise RuntimeError("Không có backend băm mật khẩu (cài pwdlib)")
```

Delete the `passlib` import block and `_legacy_context`. In `pyproject.toml` delete the `"passlib[bcrypt]>=1.7.4"` line, keep `"pwdlib[bcrypt]>=0.2"` and `"bcrypt>=4.1"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_password_backend.py tests/test_auth.py -q`
Expected: PASS. If old DB rows used passlib hashes, `verify_password` returns False — check `02_seed.sql` hashes are bcrypt `$2b$` (pwdlib reads them fine).

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/core/security.py backend/pyproject.toml backend/tests/test_password_backend.py
git commit -m "refactor(auth): single pwdlib bcrypt backend

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: Frontend kiosk small fixes (no query-lib migration)

**Files:**
- Modify: `frontend/lib/api.ts:565-572` (`kioskWsUrl`, `kioskWsProtocols`)
- Modify: `frontend/lib/kiosk-decisions.ts:81-104` (`boxLabel` dual-field fallback)
- Test: manual `tsc --noEmit` (repo has no frontend test runner)

**Interfaces:**
- Consumes: `process.env.NEXT_PUBLIC_API`, `localStorage detect_ai_token`
- Produces: unchanged `kioskWsUrl(scheduleId) -> string`, `boxLabel(b) -> string`

- [ ] **Step 1: Write the failing check**

```typescript
// node --input-type=module -e "
// import { boxLabel } from './lib/kiosk-decisions.ts' — repo has no TS runner,
// so the check is: boxLabel({ decision: 'CHECKED_IN', full_name: 'An', user_code: 'SV001' })
// must return '✓ An' and boxLabel({ decision: 'VERIFYING', userCode: 'SV002' }) must return 'SV002'.
// Current code passes; this task only simplifies internals, so record the baseline.
"
```

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0 baseline (if not, stop and report — do not proceed with refactor on broken types).

- [ ] **Step 2: Run check to confirm baseline**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 3: Write minimal implementation**

```typescript
export function kioskWsUrl(scheduleId: number): string {
  const token = getToken() || "";
  const base = API.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  return `${base}/api/v1/kiosk/ws?schedule_id=${scheduleId}&token=${encodeURIComponent(token)}`;
}
```

Old `API.replace(/^http/, "ws")` turns `https://x` into `wss://x` by accident of prefix (`http` + `s` stays) — the two-replace version is explicit and identical in output. In `boxLabel`, collapse the four-field fallback to:

```typescript
const name = b.fullName || b.full_name || b.userCode || b.user_code || "";
```

(Keep the input type as-is; only the body shrinks.) No TanStack Query migration — `@tanstack/react-query` is already used in report pages; full fetch-wrapper migration is out of scope for this fix pass.

- [ ] **Step 4: Run check to verify it passes**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/lib/kiosk-decisions.ts
git commit -m "refactor(kiosk-fe): explicit ws/wss replace, shrink boxLabel fallback

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8: SQL order doc + bench-output gitignore (no alembic yet)

**Files:**
- Create: `backend/sql/README.md`
- Modify: `.gitignore`
- Test: `cd backend && uv run python check_ddl.py` (existing script, must still exit 0)

**Interfaces:**
- Consumes: `backend/sql/*.sql`, `backend/check_ddl.py`
- Produces: documented apply order; no schema change

- [ ] **Step 1: Write the failing check**

Run: `ls backend/sql/ | sort`
Expected: `04_enable_pgvector.sql` and `04_face_tables.sql` collide on prefix `04_`, likewise `05_drop_face_embedding.sql` / `05_recognition_v2.sql` — apply order ambiguous. Record this as the failing condition.

- [ ] **Step 2: Confirm the collision**

Run: `ls backend/sql/*.sql`
Expected: two `04_*` and two `05_*` files (ambiguous glob order).

- [ ] **Step 3: Write minimal implementation**

`backend/sql/README.md`:

```markdown
# SQL apply order (Supabase / fresh DB)

1. `01_schema.sql` — base schema
2. `02_seed.sql` — roles, settings, demo accounts
3. `03_migrate_existing_db.sql` — bring old DBs to 01 shape
4. `04_enable_pgvector.sql` — `CREATE EXTENSION vector` (run BEFORE face tables)
5. `04_face_tables.sql` — `face_embeddings`, `face_events`
6. `05_recognition_v2.sql` — recognition v2 columns
7. `05_drop_face_embedding.sql` — drop legacy column (AFTER v2)
8. `06_pgvector_gallery.sql` — gallery version table
9. `07_minimize_face_schema.sql`
10. `08_attendance_snapshots.sql`
11. `09_split_classes_courses_admin.sql`

Do NOT rename files in this pass (Supabase may already reference names).
Full alembic migration is a separate project — see `docs/COMPLEXITY_AUDIT.md` §5.
```

Append to `.gitignore`:

```gitignore
backend/bench_*_out.txt
backend/best.pt
```

(`bench_full_out.txt`, `bench_out.txt`, `best.pt` are local artifacts, never source.)

- [ ] **Step 4: Run check to verify nothing broke**

Run: `cd backend && uv run python check_ddl.py`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add backend/sql/README.md .gitignore
git commit -m "chore(sql): document apply order, ignore local bench artifacts

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

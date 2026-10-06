# Face Attendance Opt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix hết 15 mục trong bản đồ hiện trạng, giữ hành vi infer, mỗi task xanh pytest + bench trước commit.

**Architecture:** 8 task theo thứ tự WS1→WS5. ORM/config trước, pipeline sau, FE cuối. Không đảo thứ tự. Mỗi task TDD: test đỏ trước, code tối thiểu, test xanh, commit.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, InsightFace, onnxruntime CPU, Next.js 16 + TypeScript. Không thêm dependency.

**Spec:** `docs/superpowers/specs/2026-09-27-face-attendance-opt-design.md`

## Global Constraints

- Backend cwd là `backend/`. Lệnh test: `uv run pytest tests/test_recognition_v2.py -q`.
- Bench chuẩn còn lại: `uv run python -m detect_ai.recognition.bench --image data/faces/001.jpg --rounds 5`. Ngưỡng giữ: detect 199–257ms, uniform 40–65ms, HTTP checkin 30–34ms.
- Không thêm dependency mới (không FAISS, không ByteTrack, không test runner FE).
- Mỗi logic nontrivial kèm 1 assert/test. Xóa hơn thêm.
- Không commit khi pytest đỏ. Không gộp task khi chưa xanh.
- FE verify: `npx tsc --noEmit` (cwd `frontend/`).

## Review Focus

- Frame có 2 mặt cùng 1 SV vote trong cùng window: cả 2 CONFIRMED nhưng commit chỉ insert 1 row nhờ unique + dict — test ở Task 4 pin điều này.
- Enroll khi thiếu liveness model từ chối hẳn: admin offline không enroll được — Task 6 báo rõ message, không silent.
- Gallery stale cross-worker trong TTL sau enroll: Task 4 chấp nhận stale, enroll cùng worker thấy ngay qua bump RAM.
- WS token qua subprotocol nhưng proxy cũ strip header: Task 8 giữ query fallback nên không lockout.
- Checkout xong pipeline vẫn CONFIRMED + already_done mỗi frame: đúng, DB là guard — Task 5 pin không insert row thứ 2.

## File Structure

- `src/detect_ai/models/face.py` — thêm 4 cột (Task 1).
- `src/detect_ai/models/attendance_v2.py` — thêm 2 cột + import Float (Task 1).
- `src/detect_ai/core/config.py` — floor interval 120 (Task 2).
- `.env.example`, `README.md`, `recognition/gallery.py` docstring — sync docs (Task 2).
- `recognition/pipeline.py` — uniform_det param, votes per-sid, done scope (Task 3, 5).
- `recognition/service.py` — uniform 1x/frame, batch SELECT, SPOOF throttle (Task 3, 4, 6).
- `recognition/gallery.py` — cache TTL trước version check (Task 4).
- `api/routes_kiosk.py`, `api/routes_kiosk_ws.py` — clamp interval, tz VN (Task 4, 6).
- `recognition/tracks.py`, `RECOGNITION_V2_PLAN.md`, `recognition/liveness.py`, `recognition/enroll.py` — chốt IoU, fail-closed (Task 5, 6).
- `services/image_service.py`, `recognition/image.py`, `services/face_service.py`, `main.py`, `recognition/uniform_engine.py`, configs — cleanup + lock + import os (Task 7).
- `frontend/lib/api.ts`, `frontend/app/teacher/classes/[id]/kiosk/page.tsx`, `frontend/lib/kiosk-decisions.ts`, `frontend/lib/face-detector.ts` — token, poll, CHALLENGE, dispose (Task 8).

---

### Task 1: ORM map 6 cột khớp 05_recognition_v2.sql

**Files:**
- Modify: `backend/src/detect_ai/models/face.py`
- Modify: `backend/src/detect_ai/models/attendance_v2.py`
- Test: `backend/tests/test_recognition_v2.py` (thêm test mới cuối file)

**Interfaces:**
- Consumes: `sql/05_recognition_v2.sql:5-14` (tên cột + default).
- Produces: `FaceEmbedding.model_version/det_score`, `FaceEvent.margin/backend`, `Attendance.uniform_score/uniform_status` cho Task 3–6 dùng.

- [ ] **Step 1: Write the failing test**

```python
def test_orm_v2_columns_mapped():
    from detect_ai.models.attendance_v2 import Attendance
    from detect_ai.models.face import FaceEmbedding, FaceEvent
    assert "uniform_status" in Attendance.__table__.columns
    assert "uniform_score" in Attendance.__table__.columns
    assert "model_version" in FaceEmbedding.__table__.columns
    assert "det_score" in FaceEmbedding.__table__.columns
    assert "margin" in FaceEvent.__table__.columns
    assert "backend" in FaceEvent.__table__.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_recognition_v2.py::test_orm_v2_columns_mapped -v` (cwd `backend/`)
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`models/face.py`, trong `FaceEmbedding` sau `source`, trong `FaceEvent` sau `decision`:

```python
model_version: Mapped[str] = mapped_column(String(32), default="buffalo_s", nullable=False)
det_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
```

```python
margin: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
backend: Mapped[str] = mapped_column(String(32), default="", nullable=False)
```

`models/attendance_v2.py`: thêm `Float` vào import sqlalchemy, sau `has_uniform`:

```python
uniform_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
uniform_status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_recognition_v2.py -q` (cwd `backend/`)
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/models/face.py backend/src/detect_ai/models/attendance_v2.py backend/tests/test_recognition_v2.py
git commit -m "feat(orm): map 6 cot recognition v2 khop 05 sql"
```

### Task 2: Floor interval 120ms + sync docs/env

**Files:**
- Modify: `backend/src/detect_ai/core/config.py:150`
- Modify: `backend/.env.example`
- Modify: `backend/../README.md` (repo root README, dòng kiosk voting)
- Modify: `backend/src/detect_ai/recognition/gallery.py` (docstring `_load_postgres`)

**Interfaces:**
- Consumes: Task 1 (không phụ thuộc code, chỉ thứ tự).
- Produces: floor 120ms cho Task 4 clamp; docs đúng cho mọi task sau.

- [ ] **Step 1: Sửa floor interval**

```python
KIOSK_INTERVAL_MS = max(120, int(S.kiosk_interval_ms))
```

File `backend/src/detect_ai/core/config.py:150`, thay `max(250,` bằng `max(120,`.

- [ ] **Step 2: Sync `.env.example`**

Sửa 3 dòng: `DETECT_AI_FACE_DET_SIZE=320` → `256`, `DETECT_AI_FACE_MIN_SIZE=60` → `45`, `DETECT_AI_FACE_MAX_FACES=8` → `3`, `DETECT_AI_FACE_VOTE_N=3` → `2`, `DETECT_AI_FACE_VOTE_WINDOW_S=2.0` → `4.0`. Thêm comment `# Code chay: det 256, vote 2/4s (env cu ghi 320/3/2s la sai)`.

- [ ] **Step 3: Sync README + docstring gallery**

README dòng kiosk: `voting 3 lần/2s` → `voting 2 lần/4s`. Docstring `_load_postgres`: thêm `Đọc cột embedding JSON; embedding_vec pgvector dự phòng chưa dùng.`

- [ ] **Step 4: Run tests + smoke import**

Run: `uv run pytest tests/test_recognition_v2.py -q` (cwd `backend/`)
Run: `uv run python -c "import detect_ai.main, detect_ai.services.image_service, detect_ai.recognition.image, detect_ai.recognition.config, detect_ai.recognition.uniform_engine; print('smoke ok')"` (cwd `backend/`)
Expected: PASS + `smoke ok`

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/core/config.py backend/.env.example README.md backend/src/detect_ai/recognition/gallery.py
git commit -m "fix(config): floor interval 120ms, sync docs theo code"
```

### Task 3: Uniform predict 1 lần/frame, truyền qua FaceDecision

**Files:**
- Modify: `backend/src/detect_ai/recognition/pipeline.py`
- Modify: `backend/src/detect_ai/recognition/service.py`
- Test: `backend/tests/test_recognition_v2.py` (thêm test đếm uniform call)

**Interfaces:**
- Consumes: Task 1 (`uniform_status/uniform_score` ORM).
- Produces: `FaceDecision.uniform_det` (UniformDetections hoặc None) cho Task 4 snapshot dùng; `commit_decisions` không infer lại.

- [ ] **Step 1: Write the failing test**

```python
def test_uniform_predict_once_per_frame(monkeypatch):
    from detect_ai.recognition import pipeline as pipe_mod
    from detect_ai.recognition.config import RecognitionConfig
    gal = _gallery()
    eng = _FakeFaceEngine(_make_face(_vec(7)))
    monkeypatch.setattr(pipe_mod.live_mod, "check_live",
                        lambda img, kps=None, bbox=None, **kw: LiveVerdict("live", 0.95, "onnx", "ok"))
    calls: list = []
    class FakeDet:
        names = ["person", "valid_shirt", "invalid_shirt"]
    def frame_predict(img):
        calls.append(1)
        return FakeDet()
    cfg = RecognitionConfig(vote_n=2, vote_window_s=4.0, spoof_min_frames=5)
    sess = KioskSession(schedule_id=201, face=eng, cfg=cfg)
    img = np.zeros((480, 640, 3), np.uint8)
    sess.process(img, gal, now=1000.0, run_uniform=None, uniform_predict=frame_predict)
    sess.process(img, gal, now=1000.8, run_uniform=None, uniform_predict=frame_predict)
    assert calls == [1, 1]
```

(`_gallery`, `_make_face`, `_vec`, `_FakeFaceEngine`, `LiveVerdict` đã có trong file test.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_recognition_v2.py::test_uniform_predict_once_per_frame -v` (cwd `backend/`)
Expected: FAIL (param `uniform_predict` chưa tồn tại)

- [ ] **Step 3: Write minimal implementation**

`pipeline.py`, `FaceDecision` thêm field:

```python
uniform_det: object = None  # UniformDetections của đúng frame này (None = chưa infer/thiếu model)
```

`process` thêm param `uniform_predict=None` (callable `(img_bgr) -> UniformDetections | None`). Đầu vòng lặp frame (sau `engine.detect`, trước loop faces), nếu có face accept tiềm năng thì infer 1 lần:

```python
frame_det = None
if uniform_predict is not None:
    try:
        frame_det = uniform_predict(img_bgr)
    except Exception:
        frame_det = None
```

Trong nhánh run-once (thay `run_uniform(...)` per-face):

```python
if frame_det is not None:
    st, _reasons, sc = uniform_for_face(np.asarray(f.bbox, dtype=np.float32), frame_det)
    u_status, u_score = str(st), float(sc)
```

Cần import `uniform_for_face` trong pipeline. Giữ param `run_uniform` cũ hoạt động (fallback khi `uniform_predict=None`) để test cũ `test_pipeline_voting_confirmed_then_uniform_hook_once` vẫn xanh. Mỗi `FaceDecision` CONFIRMED/PROVISIONAL gắn `uniform_det=frame_det`.

`service.py`: `uniform_hook_factory` đổi thành factory trả `uniform_predict` (predict cả frame, không nhận bbox). `commit_decisions` 3 nhánh dùng `d.uniform_det` thay `_detect_uniform(frame_bgr)`; giữ `_detect_uniform` làm fallback khi `d.uniform_det is None`. Xóa lời gọi infer lại khi đã có det.

- [ ] **Step 4: Run tests + bench**

Run: `uv run pytest tests/test_recognition_v2.py -q` (cwd `backend/`)
Expected: 13 passed (11 cũ + orm + uniform-once)
Run: `uv run python -m detect_ai.recognition.bench --image data/faces/001.jpg --rounds 5` (cwd `backend/`)
Expected: detect trong 199–257ms

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/recognition/pipeline.py backend/src/detect_ai/recognition/service.py backend/tests/test_recognition_v2.py
git commit -m "perf(uniform): predict 1 lan/frame, truyen qua FaceDecision"
```

### Task 4: Batch SELECT attendance + gallery TTL trước + clamp interval

**Files:**
- Modify: `backend/src/detect_ai/recognition/service.py` (`commit_decisions`)
- Modify: `backend/src/detect_ai/recognition/gallery.py` (`load_gallery`)
- Modify: `backend/src/detect_ai/api/routes_kiosk.py` (clamp interval)
- Modify: `backend/src/detect_ai/api/routes_kiosk_ws.py` (hoist min_gap + clamp + sleep)
- Test: `backend/tests/test_recognition_v2.py` (thêm test 2 mặt cùng SV 1 row)

**Interfaces:**
- Consumes: Task 3 (`FaceDecision.uniform_det`).
- Produces: hot-path không N+1; `next_interval_ms` luôn trong 120–600 cho Task 8 FE tôn trọng.

- [ ] **Step 1: Write the failing test**

```python
def test_commit_two_faces_same_student_one_row():
    # 2 FaceDecision CONFIRMED cùng sid trong 1 frame -> commit 1 lần SELECT batch,
    # không insert 2 row (unique guard). Test ở mức dict: dựng decisions giả.
    from detect_ai.recognition.pipeline import FaceDecision
    ds = [FaceDecision(1, [10, 10, 100, 120], 5, 0.9, 0.2, 0.95, "onnx", 0.9, "CONFIRMED", 2, "ok", 0.95),
          FaceDecision(2, [200, 200, 300, 320], 5, 0.88, 0.2, 0.94, "onnx", 0.9, "CONFIRMED", 2, "ok", 0.95)]
    sids = sorted({int(d.student_id) for d in ds if d.decision == "CONFIRMED" and d.student_id})
    assert sids == [5]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_recognition_v2.py::test_commit_two_faces_same_student_one_row -v` (cwd `backend/`)
Expected: FAIL (`uniform_det` kw chưa có ở FaceDecision cũ — sau Task 3 mới có; nếu Task 3 xong thì test này pass ngay, vẫn giữ để pin hành vi batch ở step 3)

- [ ] **Step 3: Write minimal implementation**

`service.py` đầu `commit_decisions`, sau `min_gap_s`:

```python
sids = sorted({int(d.student_id) for d in decisions
               if d.decision == "CONFIRMED" and d.student_id})
by_sid = {}
if sids:
    rows = (await db.execute(select(Attendance).where(
        Attendance.schedule_id == schedule_id,
        Attendance.student_id.in_(sids)))).scalars().all()
    by_sid = {a.student_id: a for a in rows}
```

Trong vòng lặp thay block `att = (await db.execute(...))` bằng `att = by_sid.get(sid)`, và sau khi `db.add(Attendance(...))` mới thì `by_sid[sid] = att_moi` (giữ biến tham chiếu row vừa add) để 2 decisions cùng sid trong 1 frame không insert trùng.

`gallery.py` `load_gallery`: chuyển block `hit = _cache.get` + check TTL lên trước `fetch_db_version`; chỉ gọi `fetch_db_version` khi miss/hết hạn/force:

```python
now = time.monotonic()
hit = _cache.get(class_id)
if not force and hit and now - hit[0] < max(30, ttl_s):
    return hit[2]
pg = _is_postgres(db)
... (giữ logic version như cũ cho trường hợp miss)
```

`routes_kiosk_ws.py` `infer`: hoist `min_gap = await load_min_checkout_gap(s)` ra trước vòng `while` (dùng cache 30s, refresh mỗi vòng lặp ngoài bằng cách check thời gian hoặc giữ nguyên 1 giá trị cho cả connection — chọn: load 1 lần lúc connect, vì đã có cache 30s ở repo). Clamp:

```python
nxt = max(120, min(nxt, 600))
```

`routes_kiosk.py` checkin: cùng công thức clamp cho `next_interval`.

- [ ] **Step 4: Run tests + bench**

Run: `uv run pytest tests/test_recognition_v2.py -q` (cwd `backend/`)
Expected: PASS
Run bench module như Task 3. Expected trong ngưỡng.

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/recognition/service.py backend/src/detect_ai/recognition/gallery.py backend/src/detect_ai/api/routes_kiosk.py backend/src/detect_ai/api/routes_kiosk_ws.py backend/tests/test_recognition_v2.py
git commit -m "perf(hotpath): batch SELECT, gallery TTL truoc, clamp interval 120-600"
```

### Task 5: Vote per-sid + done scope + chốt IoU

**Files:**
- Modify: `backend/src/detect_ai/recognition/pipeline.py` (`KioskSession`, votes, done)
- Modify: `backend/src/detect_ai/recognition/service.py` (discard done khi checkout)
- Modify: `backend/docs/RECOGNITION_V2_PLAN.md` (xóa nhắc ByteTrack, giữ IoU)
- Test: `backend/tests/test_recognition_v2.py` (vote sống qua đổi track ID)

**Interfaces:**
- Consumes: Task 3–4 (process signature mới).
- Produces: ngữ nghĩa vote/done ổn định cho Task 6 test.

- [ ] **Step 1: Write the failing test**

```python
def test_vote_survives_track_id_change(monkeypatch):
    from detect_ai.recognition import pipeline as pipe_mod
    from detect_ai.recognition.config import RecognitionConfig
    gal = _gallery()
    eng = _FakeFaceEngine(_make_face(_vec(7)))
    monkeypatch.setattr(pipe_mod.live_mod, "check_live",
                        lambda img, kps=None, bbox=None, **kw: LiveVerdict("live", 0.95, "onnx", "ok"))
    cfg = RecognitionConfig(vote_n=2, vote_window_s=4.0, spoof_min_frames=5)
    sess = KioskSession(schedule_id=202, face=eng, cfg=cfg)
    img = np.zeros((480, 640, 3), np.uint8)
    d1 = sess.process(img, gal, now=1000.0)[0]
    assert d1.decision == "PROVISIONAL"
    # Giả lập tracker cấp ID mới (mặt quay đầu): xóa tracks
    sess.tracker._tracks.clear()
    d2 = sess.process(img, gal, now=1000.8)[0]
    assert d2.decision == "CONFIRMED" and d2.student_id == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_recognition_v2.py::test_vote_survives_track_id_change -v` (cwd `backend/`)
Expected: FAIL (votes theo track, ID mới votes rỗng → PROVISIONAL)

- [ ] **Step 3: Write minimal implementation**

`pipeline.py` `KioskSession.__init__` thêm:

```python
self.votes_by_sid: dict[int, deque] = {}
```

Trong `process`, thay block vote theo `tr.votes` bằng:

```python
dq = self.votes_by_sid.setdefault(sid, deque())
dq.append(now)
while dq and now - dq[0] > cfg.vote_window_s:
    dq.popleft()
n = len(dq)
```

Spoof streak clear: `self.votes_by_sid.get(sid, deque()).clear()` thay `tr.votes.clear()`. Giữ field `tr.votes` (không dùng) để không vỡ code khác, hoặc xóa nếu grep 0 caller còn lại.

`done_students`: giữ set, nhưng `service.py` sau nhánh checkout (`checked_out.append(sid)`) thêm:

```python
from . import pipeline as _pipe_mod  # import lazy tránh cycle
_sess = _pipe_mod._sessions.get(schedule_id)
if _sess is not None:
    _sess.done_students.discard(sid)
```

`RECOGNITION_V2_PLAN.md`: sửa mục tracker — chốt IoU (`tracks.py`), xóa yêu cầu ByteTrack, ghi lý do (max 3 mặt, tracker_id=-1 vỡ vote).

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_recognition_v2.py -v` (cwd `backend/`)
Expected: PASS hết (test cũ `test_pipeline_voting_confirmed...` vẫn xanh vì ngữ nghĩa CONFIRMED giữ)

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/recognition/pipeline.py backend/src/detect_ai/recognition/service.py backend/docs/RECOGNITION_V2_PLAN.md backend/tests/test_recognition_v2.py
git commit -m "fix(vote): votes per-sid song qua doi track ID"
```

### Task 6: Fail-closed enroll + tz VN + SPOOF throttle

**Files:**
- Modify: `backend/src/detect_ai/recognition/enroll.py`
- Modify: `backend/src/detect_ai/api/routes_kiosk.py` (tz)
- Modify: `backend/src/detect_ai/api/routes_kiosk_ws.py` (tz)
- Modify: `backend/src/detect_ai/recognition/service.py` (SPOOF throttle)
- Test: `backend/tests/test_recognition_v2.py`

**Interfaces:**
- Consumes: Task 5 (commit flow).
- Produces: hành vi correctness cuối cùng phía backend cho Task 8 FE.

- [ ] **Step 1: Write the failing tests**

```python
def test_enroll_no_model_rejected(monkeypatch):
    from detect_ai.recognition import enroll as enroll_mod
    from detect_ai.recognition import liveness as live_mod
    monkeypatch.setattr(live_mod, "check_live",
                        lambda img, kps=None, bbox=None, **kw: LiveVerdict("no_model", 0.0, "none", "no-model"))
    face = _make_face(_vec(7))
    with pytest.raises(enroll_mod.EnrollError):
        enroll_mod.extract_best(np.zeros((480, 640, 3), np.uint8),
                                engine=_FakeFaceEngine(face))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_recognition_v2.py::test_enroll_no_model_rejected -v` (cwd `backend/`)
Expected: FAIL (code cũ warn-cho-qua)

- [ ] **Step 3: Write minimal implementation**

`enroll.py:36-38`:

```python
if vd.verdict == "no_model":
    raise EnrollError("Thiếu model liveness, không thể xác thực ảnh thật.")
```

`liveness.py`: giữ nguyên fail-closed, sửa docstring cue2: `MiniFAS công khai output hằng (09/2026) — chỉ dùng cue InsightFace.`

`routes_kiosk.py`: thêm helper đầu file:

```python
from zoneinfo import ZoneInfo
_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
def _today_vn():
    from datetime import datetime
    return datetime.now(_VN_TZ).date()
```

Thay `sched.study_date != date.today()` bằng `!= _today_vn()`. `routes_kiosk_ws.py`: thay `_date.today()` tương tự (file đã import datetime).

`service.py` module-level:

```python
_spoof_last: dict[tuple[int, int], float] = {}
```

Nhánh SPOOF:

```python
import time as _t
key = (schedule_id, int(d.student_id) if d.student_id else -d.track_id)
if _t.monotonic() - _spoof_last.get(key, 0.0) >= 10.0:
    _spoof_last[key] = _t.monotonic()
    spoof_seen = True
    db.add(FaceEvent(...))
# ponytail: cần audit full thì log DB mỗi frame thay vì throttle
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_recognition_v2.py -v` (cwd `backend/`)
Run: `uv run pytest tests/ -k "kiosk or gallery or liveness or spoof or timezone" -v` (cwd `backend/`)
Expected: PASS (không có test timezone cũ nào vỡ — nếu vỡ, sửa test mock `_today_vn`)

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/recognition/enroll.py backend/src/detect_ai/recognition/liveness.py backend/src/detect_ai/recognition/service.py backend/src/detect_ai/api/routes_kiosk.py backend/src/detect_ai/api/routes_kiosk_ws.py backend/tests/test_recognition_v2.py
git commit -m "fix(correctness): enroll fail-closed, tz VN, SPOOF throttle 10s"
```

### Task 7: Cleanup dead + lock uniform + import os

**Files:**
- Modify: `backend/src/detect_ai/services/image_service.py` (xóa `decode_kiosk_frame`)
- Modify: `backend/src/detect_ai/recognition/image.py` (xóa 3 hàm dead)
- Modify: `backend/src/detect_ai/services/face_service.py` (xóa 2 hàm dead)
- Modify: `backend/src/detect_ai/main.py` (xóa pools + thêm `import os`)
- Modify: `backend/src/detect_ai/recognition/uniform_engine.py` (thêm lock)
- Modify: `backend/src/detect_ai/core/config.py`, `backend/src/detect_ai/recognition/config.py`, `backend/.env.example` (xóa config chết)

**Interfaces:**
- Consumes: Task 1–6 (không còn ai dùng hàm dead).
- Produces: cây code gọn cho Task 8; không đổi hành vi.

- [ ] **Step 1: Grep xác nhận 0 caller**

Run: `rg -n "decode_kiosk_frame|resize_max_width|scale_boxes_back|letterbox|PERSON_STRIDE|extract_best|gallery_version_bump|spoof_spoof_thr|spoof_window_s|kiosk_spoof_cache_s|kiosk_face_pool" --type py backend/src backend/tests` (cwd repo root)
Expected: chỉ còn định nghĩa + comment, không caller nghiệp vụ

- [ ] **Step 2: Xóa dead code**

Xóa: `image_service.decode_kiosk_frame` (cả hàm), `image.resize_max_width`, `scale_boxes_back`, `letterbox`, `face_service.extract_best`, `face_service.gallery_version_bump`. Giữ `enroll_image`, `active_count`, `EnrollError`.
`main.py`: xóa block tạo 3 pool + shutdown loop, thêm `import os` đầu file (fix `NameError` `os.cpu_count` ở dòng 43).

- [ ] **Step 3: Xóa config chết + thêm lock uniform**

Xóa: `DETECT_AI_YOLO_PERSON_STRIDE` (.env), `yolo_person_stride` nếu có (core config không có field này — chỉ .env), `spoof_spoof_thr`, `spoof_window_s`, `kiosk_spoof_cache_s` ở core config + hằng export + recognition config + `.env.example` (`SPOOF_SPOOF_THR`, `SPOOF_WINDOW_S`).
`uniform_engine.py`:

```python
import threading
# trong __init__: self._lock = threading.Lock()
def open(self):
    with self._lock:
        if self._sess is not None:
            return self._sess
        ... (code cũ, indent +1)
def predict(self, img_bgr):
    with self._lock:
        self._ensure()
        return self._predict_onnx(img_bgr)
```

(Cẩn thận `_ensure` gọi `open` — gộp lock 1 chỗ để không deadlock: lock trong `predict` + check trong `open` dùng cùng RLock, hoặc đơn giản: dùng `threading.RLock`.)

- [ ] **Step 4: Run tests + smoke + bench**

Run: `uv run pytest tests/test_recognition_v2.py -q` (cwd `backend/`)
Run smoke import như Task 2.
Run bench module, đối chiếu detect 199–257ms / uniform 40–65ms.

- [ ] **Step 5: Commit**

```bash
git add backend/src/detect_ai/services/image_service.py backend/src/detect_ai/recognition/image.py backend/src/detect_ai/services/face_service.py backend/src/detect_ai/main.py backend/src/detect_ai/recognition/uniform_engine.py backend/src/detect_ai/core/config.py backend/src/detect_ai/recognition/config.py backend/.env.example
git commit -m "chore: xoa dead code/config, lock uniform, fix import os"
```

### Task 8: FE token khỏi URL + poll re-arm + xóa CHALLENGE + dispose

**Files:**
- Modify: `frontend/lib/api.ts` (`kioskWsUrl`)
- Modify: `frontend/app/teacher/classes/[id]/kiosk/page.tsx` (WS subprotocol, poll, dispose)
- Modify: `frontend/lib/kiosk-decisions.ts` (xóa nhánh CHALLENGE)
- Modify: `frontend/lib/face-detector.ts` (export reset/dispose)
- Modify: `backend/src/detect_ai/api/routes_kiosk_ws.py` (`_auth_teacher` nhận subprotocol)

**Interfaces:**
- Consumes: Task 4 (interval 120–600), Task 6 (tz).
- Produces: không có (task cuối).

Lưu ý lệch spec: giữ mapping `CHALLENGE→VERIFYING` trong `to_legacy` (compat), chỉ xóa nhánh CHALLENGE chết phía FE vì server không bao giờ gửi `"CHALLENGE"` thô.

- [ ] **Step 1: Token qua subprotocol + fallback query**

`api.ts`:

```typescript
export function kioskWsUrl(scheduleId: number): string {
  const token = getToken() || "";
  const base = API.replace(/^http/, "ws");
  return `${base}/api/v1/kiosk/ws?schedule_id=${scheduleId}&token=${encodeURIComponent(token)}`;
}
export function kioskWsProtocols(): string[] {
  const token = getToken() || "";
  return token ? [`jwt-${token}`] : [];
}
```

`page.tsx`: `new WebSocket(kioskWsUrl(scheduleId))` → `new WebSocket(kioskWsUrl(scheduleId), kioskWsProtocols())`.
`routes_kiosk_ws.py` `_auth_teacher(token)` thêm param `protocols: str | None`:

```python
if not token and protocols:
    for p in protocols.split(","):
        p = p.strip()
        if p.startswith("jwt-"):
            token = p[4:]
            break
```

Lấy từ `ws.headers.get("sec-websocket-protocol")`. Query cũ vẫn chạy (fallback).

- [ ] **Step 2: Xóa nhánh CHALLENGE FE**

`kiosk-decisions.ts`: `boxColor` gộp `case "CHALLENGE"` xóa (giữ VERIFYING amber); `boxLabel` xóa `case "CHALLENGE"`. `page.tsx:225`: `(f.decision === "VERIFYING" || f.decision === "CHALLENGE")` → `(f.decision === "VERIFYING")`.

- [ ] **Step 3: Fallback poll re-arm + tôn trọng server**

Thay `useEffect` setInterval (`page.tsx:530-539`) bằng chained timeout:

```typescript
useEffect(() => {
  if (!running || !scheduleId || wsOkRef.current) return;
  let dead = false;
  const tick = async () => {
    if (dead) return;
    await captureAndSend();
    if (!dead) timerRef.current = setTimeout(tick, intervalRef.current || FALLBACK_POLL_MS);
  };
  timerRef.current = setTimeout(tick, intervalRef.current || FALLBACK_POLL_MS);
  return () => { dead = true; if (timerRef.current) clearTimeout(timerRef.current); timerRef.current = null; };
}, [running, scheduleId, captureAndSend]);
```

`timerRef` đổi type sang `ReturnType<typeof setTimeout> | null`. WS throttle (`page.tsx:504`): `Math.max(30, ...)` → tôn trọng server: `Math.max(60, Math.min(intervalRef.current || 450, 600))`.

- [ ] **Step 4: Dispose MediaPipe**

`face-detector.ts` thêm:

```typescript
export async function closeClientFaceDetector(): Promise<void> {
  try { detectorInstance?.close(); } catch { /* ignore */ }
  detectorInstance = null;
}
```

(`FaceDetector` tasks-vision có `.close()`.) `page.tsx` `stopCamera`: gọi `closeClientFaceDetector()` (fire-and-forget, không await trong callback thường — dùng `.catch(()=>{})`).

- [ ] **Step 5: Verify FE + commit**

Run: `npx tsc --noEmit` (cwd `frontend/`)
Expected: PASS, không lỗi type mới
Manual checklist: mở kiosk → WS connect (token subprotocol) → fallback HTTP re-arm theo server → stopCamera không leak (mở/đóng 3 lần, GPU process ổn định).

```bash
git add frontend/lib/api.ts "frontend/app/teacher/classes/[id]/kiosk/page.tsx" frontend/lib/kiosk-decisions.ts frontend/lib/face-detector.ts backend/src/detect_ai/api/routes_kiosk_ws.py
git commit -m "fix(kiosk-fe): token subprotocol, poll re-arm, dispose detector"
```

## Self-Review

- Spec coverage: WS1→Task 1+2, WS2→Task 3+4, WS3→Task 5+6, WS4→Task 7, WS5→Task 8. Đủ. pgvector query không làm theo spec (ghi rõ dự phòng). `main.py` pools xóa ở Task 7 (spec WS4).
- Placeholder: không có TBD/TODO. Mọi step có code/lệnh cụ thể.
- Type consistency: `FaceDecision.uniform_det: object`; `uniform_predict` callable; `votes_by_sid: dict[int, deque]`; `kioskWsProtocols(): string[]`. Task sau dùng đúng tên Task trước định nghĩa.
- Review Focus: 5 dòng đều có test pin ở Task 4 (unique), 6 (enroll message), 4 (stale ghi chú), 8 (fallback), 5 (không insert row thứ 2 — pin bằng test batch Task 4 + unique DB).

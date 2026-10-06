# Face attendance opt — design (2026-09-27)

> Nguồn: `docs/face-attendance-current-map.md` (15 mục) + đo thật 27/09 CPU Win (detect 199-257ms, liveness 13.8ms steady, uniform 40-65ms, HTTP overhead 30-34ms, 11 tests pass). Judge panel 3 góc (latency/correctness/cleanup) merge 5 WS. User duyệt WS1-5.

## Mục tiêu + phi mục tiêu

- Mục tiêu: fix hết 15 mục map. Giữ hành vi infer. Xóa hơn thêm. Mỗi WS verify pytest + bench + tsc trước commit.
- Phi mục tiêu: đổi model/threshold nhận diện. ByteTrack (chốt IoU, xem WS3). pgvector query (ghi rõ dự phòng, chưa bật).

## Thứ tự

WS1 → WS2 → WS3 → WS4 → WS5. Lý do: ORM/config trước, pipeline sau, FE cuối. Không đảo.

## WS1 — nền: ORM + config + docs

Scope: map 6 cột ORM khớp `sql/05_recognition_v2.sql`, floor interval 120ms, sync docs/env. Không đổi infer.

Steps:
1. `models/face.py`: `FaceEmbedding.model_version` String(32) default `buffalo_s`, `det_score` Float 0.0 (khớp SQL:5-6).
2. `models/attendance_v2.py`: `Attendance.uniform_score` Float 0.0, `uniform_status` String(20) default `unknown` (khớp SQL:9-10).
3. `models/face.py`: `FaceEvent.margin` Float 0.0, `backend` String(32) default `''` (khớp SQL:13-14).
4. `core/config.py:150`: floor `max(250,…)` → `max(120,…)` cho khớp clamp WS 120ms.
5. Sync `.env.example` + `README.md` theo code: det 256, min 45, max 3, vote 2/4s. Sửa docstring gallery `_load_postgres`: đọc JSON cột `embedding`, `embedding_vec` pgvector dự phòng chưa dùng.
6. Smoke import main, image_service, recognition.image/config/uniform_engine.

Risks: DB chưa migrate 05 → chạy doctor trước. `.env` cũ giữ giá trị cũ, code thắng.
Tests: `uv run pytest tests/test_recognition_v2.py -q` (cwd backend).

## WS2 — hot-path latency

Scope: giết N+1 SELECT, 3 infer uniform, 1 RTT gallery/frame, overshoot interval.

Steps:
1. `service.py` + `pipeline.py`: uniform predict 1 lần/frame trong `process`, truyền `UniformDetections` qua `FaceDecision` sang `commit_decisions` + snapshot. Xóa `_detect_uniform` infer lại 3 nhánh commit (`service.py:145,174,191`).
2. `pipeline.py:88`: `process` nhận `uniform_det`, hook per-face thành `uniform_for_face` thuần, giữ run-once qua `tr.uniform_done` (`pipeline.py:169-181`).
3. `commit_decisions`: 1 SELECT `WHERE schedule_id=:sid AND student_id IN (:sids)` trước vòng lặp, dict theo sid.
4. `gallery.py:113-129`: check `_cache` TTL trước, chỉ `fetch_db_version` khi miss/hết hạn.
5. `routes_kiosk_ws.py`: hoist `load_min_checkout_gap` khỏi per-frame, clamp `nxt` 120–600, sleep phần dư server-side.
6. `routes_kiosk.py`: clamp interval giống WS.
7. Bench mỗi bước, dừng nếu detect lệch 199–257ms hay uniform lệch 40–65ms.

Risks: gallery stale trong TTL (enroll dùng force). Double check-in 2 worker (unique `uq_attendance_schedule_student` + 409 ở `main.py` cứu).
Tests: pytest + bench repeats 20 + assert `next_interval_ms >= 120`.

## WS3 — correctness: vote, liveness, tz, spoof

Scope: chốt IoU, vote per-sid, fail-closed, múi giờ VN, throttle SPOOF, done scope in/out.

Steps:
1. Chốt `tracks.py` IoU, xóa nhắc ByteTrack khỏi `RECOGNITION_V2_PLAN.md:8-10` (mâu thuẫn note `tracks.py:1-8`). Vote key per-sid window; track chỉ smooth liveness; đổi ID không reset CONFIRMED.
2. `pipeline.py:76,182-184`: `done_students` scope in/out, xóa khi checkout xong, không giữ hết TTL 2h.
3. `liveness.py`: giữ fail-closed `no_model` → REJECTED. MiniFAS hằng không dùng (`liveness.py:132-136`), ghi rõ 1 cue InsightFace.
4. `enroll.py:36-38`: `no_model` warn-cho-qua → reject `EnrollError`.
5. Kiosk HTTP + WS: `date.today()` → `_today_vn` Asia/Ho_Chi_Minh theo `routes_teacher.py:34-38` (`routes_kiosk.py:97`, `routes_kiosk_ws.py:96`).
6. `service.py:206-209`: `FaceEvent` SPOOF throttle 1 sid/10s dict local. Xóa `kiosk_spoof_cache_s` chết. `ponytail:` bật DB log full khi cần audit.
7. Mỗi logic nontrivial +1 assert/test.

Risks: test cũ mock `date.today` vỡ, hành vi quanh 00:00 đổi, throttle mất granularity audit, tăng max_faces vỡ interval CPU.
Tests: pytest `-v`, `-k 'kiosk or gallery or liveness or spoof or timezone'`, bench.

## WS4 — cleanup dead + lock

Scope: xóa dead, thêm lock uniform, giữ hành vi.

Steps:
1. Grep 0-caller trước xóa: `decode_kiosk_frame`, `resize_max_width`, `scale_boxes_back`, `letterbox`, `PERSON_STRIDE`, `face_service.extract_best`, `gallery_version_bump`, `YOLO_PERSON_STRIDE`, `spoof_spoof_thr`, `spoof_window_s`, `kiosk_spoof_cache_s`.
2. Xóa hàm dead (`image_service.py:37`, `image.py:60,71,84`, `face_service.py:19,31`). Giữ `enroll_image`, `active_count`, `EnrollError`.
3. Xóa 3 pool `main.py:46-48` + shutdown loop. Fix `NameError` `os.cpu_count` (`main.py:43`, thiếu `import os` — crash lifespan thật).
4. Xóa config chết 2 file + `.env.example`.
5. `uniform_engine.py`: thêm `threading.Lock` cho `open` + `predict` theo mẫu `FaceEngine._infer_lock`. Đo CPU 0 lỗi/16 concurrent — guard phòng EP GPU.
6. Smoke import + pytest hồi quy.

Risks: script ngoài repo import hàm chết vỡ import. Lock uniform serialize infer GPU (overhead nhỏ, đo lại khi bật EP GPU).
Tests: pytest + grep dead names + bench đối chiếu.

## WS5 — FE + WS signal + auth

Scope: token khỏi URL, xóa nhánh CHALLENGE chết, tôn trọng interval server, dispose MediaPipe.

Steps:
1. `api.ts:565-569` + `routes_kiosk_ws.py:39-62`: token qua `Sec-WebSocket-Protocol`/first-message, giữ query fallback ngắn hạn.
2. Xóa CHALLENGE: `service.py:94`, `kiosk-decisions.ts:72,101`, `page.tsx:225` — server map VERIFYING, FE không bao giờ nhận `"CHALLENGE"`.
3. Fallback poll: `setInterval` cứng (`page.tsx:533`) → chained `setTimeout` re-arm từ `next_interval_ms`, reset khi có WS msg, backoff khi lỗi, xóa timer thừa khi WS mở (`page.tsx:243`). Bỏ floor 30ms, tôn trọng server 120–600.
4. `stopCamera` (`page.tsx:322-339`): dispose detector, hết leak GPU.
5. `tsc --noEmit` + test kiosk-decisions + assert WS live.

Risks: client cũ còn `?token=` cần fallback. Snapshot test cũ vỡ.
Tests: `npx tsc --noEmit` (cwd frontend) + node test kiosk-decisions + wscat assert interval 120–600.

## Verify chung mỗi WS

- `cd backend && uv run pytest tests/test_recognition_v2.py -q`
- bench lệch mới dừng review (detect 199–257ms, uniform 40–65ms, HTTP 30–34ms)
- WS5 thêm `cd frontend && npx tsc --noEmit`
- Không commit khi đỏ. Không gộp WS khi chưa xanh.

# Bản đồ điểm danh khuôn mặt — hiện trạng (2026-09-27)

> Nguồn chính: code `backend/src/detect_ai/recognition/*`, `backend/src/detect_ai/api/routes_kiosk*.py`, `frontend/app/teacher/classes/[id]/kiosk/page.tsx`, `frontend/lib/*`, `docs/RECOGNITION_V2_PLAN.md`. Chưa đề xuất fix, chỉ map để tối ưu sau.

## 1. Luồng end-to-end

### 1a. Mở kiosk (frontend)
1. GV mở `frontend/app/teacher/classes/[id]/kiosk/page.tsx:48` (`KioskPage`). `liveQuery` gọi `getTeacherLiveAttendance` mỗi 5s (`page.tsx:98-104`) lấy `schedule_id` hôm nay. Không có tiết → `scheduleId=null`, kiosk đóng (`page.tsx:297-301`, `617-622`).
2. Bấm "Mở camera" → `getUserMedia 1280x720` (`page.tsx:302-306`), init MediaPipe lazy `getClientFaceDetector()` (`page.tsx:313-315`).
3. Check gallery: `getKioskGalleryStatus(classId)` (`page.tsx:106-113`, `api.ts:595-597`) → hiện `enrolled/total` (`page.tsx:755-761`).

### 1b. Capture + transport (frontend → backend)
- Ưu tiên WS `kioskWsUrl(scheduleId)` với `?schedule_id=&token=` (`api.ts:565-569`, `page.tsx:411`). Ping-pong 1-in-flight: `inFlightRef`, timeout 2s, throttle `max(30,min(interval,120))` (`page.tsx:418-456`, `503-506`).
- Frame: canvas resize `targetW=widthRef (480 default)` JPEG q0.6 (`page.tsx:436-455`).
- Overlay 60 FPS: `detectForVideo` mỗi rAF → `matchServerIdentities` ghép nhãn server trễ 200-400ms vào box local (`page.tsx:342-401`, `face-detector.ts:96-181`).
- Fallback HTTP khi WS chưa mở: `setInterval(captureAndSend, intervalRef)` POST `kioskCheckin(scheduleId, blob)` (`page.tsx:239-293`, `530-539`, `api.ts:585-593`).
- Ổn định UI: `stabilizeDecisions` (đổi màu sau 2 msg hoặc >800ms, SPOOF 1200ms), `filterFreshChecked` cooldown 12s/người (`kiosk-decisions.ts:15-65`, `page.tsx:197-209`).

### 1c. Infer server
HTTP `POST /api/v1/kiosk/checkin` (`routes_kiosk.py:102-169`):
1. `_get_schedule_for_teacher` gate: đúng teacher, `study_date == today` (`routes_kiosk.py:82-99`).
2. `decode_frame(content, kiosk_max_width)` cv2 fast-path, reject >5MB (`routes_kiosk.py:111-117`, `image.py:44-57`).
3. `load_gallery(db, class_id)` (`routes_kiosk.py:119`). Rỗng → trả `gallery_size=0`.
4. Single-flight per schedule: `lock.locked()` → bỏ frame, trả `next_interval+200` (`routes_kiosk.py:124-129`).
5. `asyncio.to_thread(sess.process, img, gallery, None, uniform_hook_factory())` (`routes_kiosk.py:135-136`).
6. Map `to_legacy`, `commit_decisions`, trả `next_interval_ms/next_width` adaptive theo `infer_ms` (`routes_kiosk.py:139-169`).

WS `/api/v1/kiosk/ws` (`routes_kiosk_ws.py:65-210`): auth JWT query (`_auth_teacher:39-62`), gate ngày (`95-99`), load gallery 1 lần lúc connect (`101`), queue `latest maxsize=1` drop cũ (`109-133`), `infer` loop decode → `sess.process` → `commit_decisions` → JSON `{faces, checked_in/out, already_done, infer_ms, next_interval_ms, next_width, dropped, gallery_size}` (`135-195`).

### 1d. Pipeline `KioskSession.process` (`pipeline.py:88-196`)
1. `gallery` rỗng → `[]`. `FaceEngine.detect` → `list[Face]` (`95-98`).
2. `IoUTracker.update(boxes, now)` → `track_id` (`99`, `tracks.py:42-91`).
3. Gate: `det_score < 0.15` → LOWQ; `quality() < 0.35` → LOWQ (`109-118`, `face_engine.py:141-159`).
4. `gallery.match(emb, thr=0.45, unsure_low=0.35, margin_min=0.05)`: non-accept → UNKNOWN/PROVISIONAL (`121-127`, `gallery.py:238-263`).
5. `liveness.check_live(img, kps, bbox)` lazy chỉ candidate accept (`130-131`, `liveness.py:178-213`):
   - `no_model` → REJECTED (fail-closed). `rejected` → PROVISIONAL. `spoof` streak ≥2 → SPOOF + clear votes. `challenge` (0.55-0.8) → CHALLENGE. `live_ema < 0.8` → PROVISIONAL.
6. Vote: append `(now,sid)`, tỉa ngoài `vote_window_s=4s`, đếm `n` cùng sid. `n >= vote_n=2` và chưa `done` → CONFIRMED (`164-187`).
7. Uniform run-once khi `n >= vote_n-1`, cache `uniform_done[sid]` (`169-181`, `service.py:39-62`, `uniform_engine.py:175-224`).
8. GC tracks `last_seen > 30s` (`193-195`). Session TTL 2h (`pipeline.py:217-224`).

### 1e. Commit `commit_decisions` (`service.py:111-212`)
- CONFIRMED đầu → insert `Attendance(PRESENT, face-kiosk-v2)` + snapshot in + `FaceEvent CHECKED_IN` (`142-158`).
- `att.check_in_time is None` → điền giờ, snapshot nếu thiếu (`163-183`).
- Đã check-in, `check_out None`, `elapsed >= min_gap (5 phút)` → `check_out=now` + snapshot out + `FaceEvent CHECKED_OUT` (`184-200`).
- Đã đủ in+out → `already_done`. `is_manual_override` → không ghi đè (`159-162`, `202-205`).
- SPOOF → `FaceEvent SPOOF` mỗi frame (`206-209`). Commit khi `changed or spoof_seen` (`210-211`).
- `has_uniform`: `unknown/ok → True`, `violation → False`, note `+uniform-violation` (`137-140`).
- Snapshot: `_detect_uniform(frame)` + `save_attendance_snapshot` vẽ khung mặt + áo + timestamp, tối đa 2 ảnh/người/tiết (`image_service.py:104-...`, `service.py:143-148`).

### 1f. Enroll/gallery
- Admin upload: `POST /kiosk/enroll/{user_id}` (require_admin) → `decode_strict` → `enroll_image(source=kiosk)` (`routes_kiosk.py:205-229`, `enroll.py:42-72`). Gate: `quality >= 0.40`, liveness spoof reject, `no_model` cho qua warn (`enroll.py:24-39`). Giữ max 5 vector/SV, bump version RAM + DB (`enroll.py:51-69`).
- Backfill: `POST /kiosk/backfill` quét `data/storage/avatars/<code>.jpg`, skip đã có vector (`routes_kiosk.py:232-274`).
- Gallery: multi-prototype, không mean-pool. Matrix `(N_protos,512)` cosine `matrix @ v`, margin `top1-top2` (`gallery.py:223-263`). Cache versioned per class, TTL 300s (`gallery.py:113-129`). HTTP `fetch_db_version` mỗi request Postgres (`gallery.py:117`); WS load 1 lần lúc connect — enroll giữa ca WS không thấy trừ khi reset. LƯU Ý: `iou_thr` truyền vào `uniform_for_face` KHÔNG được dùng trong hàm (`uniform_engine.py:176` — dead param).
- DB: `face_embeddings(user_id, embedding JSON 512, quality, source, is_active)` + idx user_active (`models/face.py:9-31`). Migration `05_recognition_v2.sql` thêm `model_version/det_score` + `attendance.uniform_score/uniform_status` + `face_events.margin/backend` — model SQLAlchemy (`face.py`, `attendance_v2.py`) CHƯA map 6 cột này (drift ORM↔SQL). `06_pgvector_gallery.sql` thêm `embedding_vec vector(512)` + HNSW + `gallery_versions` (multi-worker). `face_events` audit (`models/face.py:34-53`). `attendance` unique (schedule, student) (`models/attendance_v2.py:76-80`).

## 2. File/symbol + vai trò

| File | Symbol | Vai trò |
|---|---|---|
| `backend/src/detect_ai/api/routes_kiosk.py:102` | `kiosk_checkin` | HTTP 1 frame → decisions. Single-flight, adaptive feedback |
| `backend/src/detect_ai/api/routes_kiosk.py:72` | `_lock_for` | Lock per schedule, chống infer chồng |
| `backend/src/detect_ai/api/routes_kiosk.py:82` | `_get_schedule_for_teacher` | Gate teacher + đúng ngày |
| `backend/src/detect_ai/api/routes_kiosk.py:172` | `gallery_status` | Đếm enrolled/total per class |
| `backend/src/detect_ai/api/routes_kiosk.py:205,232,277` | `enroll_face/backfill/reset_session` | Enroll admin-only, backfill avatar, xóa voting RAM |
| `backend/src/detect_ai/api/routes_kiosk_ws.py:65,114,135` | `kiosk_ws/recv/infer` | WS latest-only, 2 task riêng |
| `backend/src/detect_ai/recognition/pipeline.py:66,88` | `KioskSession/process` | Voting, liveness smoothing, uniform run-once |
| `backend/src/detect_ai/recognition/pipeline.py:34,203,217` | `FaceDecision/_shared_engine/get_session` | DTO, singleton FaceEngine, session per schedule TTL 2h |
| `backend/src/detect_ai/recognition/face_engine.py:35,90` | `FaceEngine/detect` | InsightFace buffalo auto GPU→L, resize max_width 480, max 3 mặt |
| `backend/src/detect_ai/recognition/face_engine.py:141` | `quality()` | 0.5 det + 0.35 sharp (Laplacian/120) + 0.15 sáng |
| `backend/src/detect_ai/recognition/gallery.py:113,238` | `load_gallery/match` | Cache versioned, match top1/top2 + margin |
| `backend/src/detect_ai/recognition/tracks.py:42` | `IoUTracker.update` | Greedy IoU 0.3, TTL 2s, gán track_id |
| `backend/src/detect_ai/recognition/liveness.py:178` | `check_live` | Fusion InsightFace + MiniFAS optional, fail-closed |
| `backend/src/detect_ai/recognition/uniform_engine.py:80,175` | `UniformEngine/uniform_for_face` | YOLO ONNX tay, gán áo qua person-chứa-face |
| `backend/src/detect_ai/recognition/service.py:39,65,89,111` | `uniform_hook_factory/_detect_uniform/to_legacy/commit_decisions` | Hook run-once, snapshot detect, map v2→cũ, upsert 2 lượt/tiết |
| `backend/src/detect_ai/recognition/enroll.py:24,42` | `extract_best/enroll_image` | Enroll quality + liveness gate, max 5 vector |
| `backend/src/detect_ai/recognition/image.py:27,44,60,71,77,84` | `decode_strict/decode_frame/resize_max_width/scale_boxes_back/encode_jpeg/letterbox` | 1 cổng decode (cv2 kiosk, Pillow enroll). `resize_max_width/scale_boxes_back/letterbox` 0 caller — dead |
| `backend/src/detect_ai/recognition/config.py:32,85,138` | `RecognitionConfig/get_config/auto_tune` | Mọi ngưỡng 1 chỗ, env RECOGNITION_* fallback core |
| `backend/src/detect_ai/services/image_service.py:104` | `save_attendance_snapshot` | Vẽ snapshot bằng chứng, local `/static/storage` |
| `backend/src/detect_ai/services/face_service.py:1` | compat wrapper | Giữ API cũ, ruột recognition v2 |
| `backend/src/detect_ai/models/face.py:9,34` | `FaceEmbedding/FaceEvent` | Vector JSON + audit decisions |
| `backend/src/detect_ai/models/attendance_v2.py:31` | `Attendance` | 1 row/tiết/SV, unique (schedule, student) |
| `frontend/app/teacher/classes/[id]/kiosk/page.tsx:48,239,404` | `KioskPage/captureAndSend/WS effect` | Camera, MediaPipe 60FPS loop, WS 1-in-flight, fallback HTTP |
| `frontend/lib/face-detector.ts:6,96` | `getClientFaceDetector/matchServerIdentities` | BlazeFace GPU→CPU, IoU match 0.3, nhớ prev 0.8s/IoU 0.4 |
| `frontend/lib/kiosk-decisions.ts:15,56` | `stabilizeDecisions/filterFreshChecked` | Hysteresis 2 msg/800ms, cooldown lịch sử 12s |
| `frontend/lib/api.ts:543,585,565` | `KioskFaceBox/kioskCheckin/kioskWsUrl` | Contract FE-BE |
| `docs/RECOGNITION_V2_PLAN.md:1` | plan hybrid | Spec chưa làm: ByteTrack, YOLO(), InsightFace 2.0 addons observe |

## 3. Config/ngưỡng hiện tại

`recognition/config.py:32-71` (default CPU 4-core):
- Face: `pack auto` (auto_tune: GPU→buffalo_l, CPU→buffalo_s), `det_size 256`, `thr 0.45`, `margin_min 0.05`, `unsure_low 0.35`, `min_size 45px`, `max_faces 3` (code + `core/config.py:42-49`). Drift: `.env.example:52,59-60` ghi `det 320/min 60/max 8` — cũ, sai so với code
- Vote: `vote_n 2`, `vote_window 4.0s` (code). Drift: `.env.example:57-58` ghi `3/2.0s`, `README.md:14` ghi `3 lần/2s` — cũ, sai so với code
- Quality: `quality_min 0.35`, `det_score_min 0.15`
- Liveness: `live_thr 0.80`, `spoof_spoof_thr 0.65` + `spoof_window_s 2.0` định nghĩa nhưng pipeline KHÔNG đọc (dead config, `core/config.py:52-54`, `recognition/config.py:51-53`), `spoof_min_frames 2`, `challenge_low 0.55`, `spoof_model ""`, `minifas ""`. `kiosk_spoof_cache_s 10.0` (`core/config.py:61`) định nghĩa nhưng KHÔNG ai đọc (dead config)
- Gallery: `cache_ttl 300s`
- Kiosk: `max_width 480`, `interval 450ms`
- Uniform: `conf 0.35`, `imgsz 384`, `provider auto`, `iou_thr 0.30`
- Session/track: `session_ttl 7200s`, `track_ttl 2.0s`, `track_iou 0.30`
- Commit: `MIN_CHECKOUT_GAP 5 phút` (`service.py:36`), `load_min_checkout_gap` cache RAM 30s (`settings_repo.py:48-64`), DB `CHECKOUT_MIN_GAP_MINUTES` seed 5 (`02_seed.sql:105`, `08_attendance_snapshots.sql:9`)
- Enroll: `MIN_QUALITY 0.40`, `MAX 5 vector/SV` (`enroll.py:16-17`)
- FE: `FALLBACK_POLL 450ms`, WS throttle clamp `30-120ms` (`page.tsx:43,504`), IoU server-match `0.3`, prev `0.4/800ms`, stabilize `2 msg/800ms (SPOOF 1200ms)`, history cooldown `12s`
- Transport: frame JPEG `480px q0.6`, giới hạn `5MB`, infer chậm `>500ms +100 interval`, `>800ms +250 & width 416`

## 4. Nghẽn/rủi ro cho vòng tối ưu

1. Uniform infer thừa — ĐO THẬT 27/09 (CPU, 1280×720, `yolo26n.onnx`): hook 65.1ms, 1 call/4 frames (cache `uniform_done` đúng). Tổng/người/tiết = hook 1 + commit check-in 1 + commit check-out 1 = 3 YOLO (~40-65ms mỗi lần) cho 2 quyết định. Commit không dùng cache pipeline, infer lại cùng frame. Fix = truyền `uniform_det` từ pipeline sang commit, xóa 1-2 infer.
2. `commit_decisions` SELECT `Attendance` từng decision từng frame (`service.py:133-134`). `load_min_checkout_gap` cache RAM 30s — không storm. ĐO THẬT 27/09 (SQLite in-mem, gallery 30 SV/90 vec, frame đen, infer fake): checkin 30-34ms/req ổn định ×5; `gallery-status` 257ms (1 lần). Overhead HTTP+DB thuần ~30ms — chấp nhận được ở quy mô lớp. Storm N SELECT chỉ đau khi đông mặt + Postgres latency cao.
3. HTTP load gallery mỗi frame, Postgres còn `fetch_db_version` mỗi request (`gallery.py:117`). WS đỡ (load 1 lần) → HTTP yếu hơn WS đúng chỗ cache.
4. `IoUTracker` greedy không ReID/memory (`tracks.py:42-91`): ID đổi → `_Track` mới votes rỗng → CONFIRMED chậm lại từ đầu. `RECOGNITION_V2_PLAN.md:8-10` tự ghi nhận. Note `tracks.py:1-8` cố ý bỏ ByteTrack (max 3 mặt, sợ tracker_id=-1), plan vẫn đòi ByteTrack lại — 2 doc mâu thuẫn, chưa chốt.
5. Liveness fail-closed khi thiếu model (`liveness.py:192-197` → REJECTED). MiniFAS public output hằng, không dùng (`liveness.py:132-136`). Thực tế 1 cue InsightFace. ĐO THẬT 27/09: model tồn tại `~/.insightface/addons/liveness.onnx`, ảnh thật verdict=live score=1.0 backend=onnx-insightface. Fail-closed chưa kích hoạt trên máy dev.
6. `_uniform` global init không lock (double-create benign) + `UniformEngine._sess` ONNX infer không lock (`uniform_engine.py:116-118`; `FaceEngine` có `_infer_lock`, uniform không). Test race 27/09: 8 threads × 16 `U.predict` = 0 lỗi, 4×8 `eng.detect` = 0 lỗi trên CPUExecutionProvider (máy dev Win, ORT thread-safe ở mức này). Rủi ro còn trên EP GPU (CUDA/DML arena) + init race — hạ từ "race" xuống "thiếu guard, chưa crash trên CPU". Thêm: `main.py:46-48` tạo 3 pool nhưng routes KHÔNG dùng (dead), vẫn `asyncio.to_thread` default.
7. `FaceEvent SPOOF` insert mỗi frame spoof (`service.py:206-209`) → phình bảng khi camera đứng yên trước ảnh giả.
8. `done_students` giữ tới hết TTL 2h, không xóa khi checkout (`pipeline.py:76,182-184`) → frame sau vẫn CONFIRMED, dựa `already_done` để khỏi spam.
9. Fallback HTTP adaptive hỏng: `setInterval` lập 1 lần lúc mount, deps `[running, scheduleId, captureAndSend]` nhưng `captureAndSend` chỉ đổi khi `scheduleId/handleFaces` đổi (`page.tsx:530-539,239`) → `next_interval` server trả (`page.tsx:260`) không re-arm interval đang chạy. `captureAndSend` còn `return` sớm khi WS mở (`page.tsx:243`) nên timer chạy thừa mỗi tick. WS ping-pong đúng (`page.tsx:458-510`): throttle `min(interval,120)` + timeout 2s, nhưng floor 30ms → infer chậm server dặn 700ms vẫn bị clamp 120ms, gửi dày ~6x ý định.
10. `max_faces 3` nghẽn cửa lớp đông. ĐO THẬT 27/09 (CPU Win, buffalo_s, det 256, ảnh thật 1280×720): detect 199-257ms/frame (warm 350ms), liveness 13.8ms steady (102ms lần đầu load model), uniform 40-50ms, match 0.001ms (gallery 100 proto). Pipeline full frame0 381ms (detect+liveness+uniform) → frame1 CONFIRMED 200ms. Tổng chốt ~580ms/2 frames sau warmup — dưới vote window 4s, kịp 450ms interval. `det_size 256` đủ, không cần 320 trên CPU.
11. Token teacher trong URL WS (`api.ts:568`) lọt log/proxy. Enroll/backfill require_admin đúng, kiosk require_teacher + gate teacher + ngày. Thêm: gate ngày dùng `date.today()` server-local (`routes_kiosk.py:97`, `routes_kiosk_ws.py:96`) trong khi `routes_teacher.py:34-38` dùng `Asia/Ho_Chi_Minh` — lệch múi giờ khi deploy UTC (kiosk đóng/mở sai quanh nửa đêm).
12. Snapshot vẽ Pillow tay full frame (`image_service.py:104-245`), mount `/static/storage` (`main.py:116-117`), KHÔNG sync Supabase (doc supabase.py:16-17 xác nhận bucket snapshots bỏ legacy). `DETECT_AI_YOLO_PERSON_STRIDE=3` (`.env.example:33`) + `letterbox()` (`image.py:84`) không ai gọi (dead). Plan đề xuất `sv.BoxAnnotator` chưa làm.
13. MediaPipe CDN (`face-detector.ts:13-22,32-33`): wasm jsdelivr + tflite storage.googleapis. Offline/chặn → `null`, fallback server boxes. Module giữ `detectorInstance` singleton nhưng `page.tsx:313-314` không check trước khi gọi, `stopCamera` (`page.tsx:322-339`) không dispose detector → GPU delegate leak qua nhiều lần mở cam.
14. Uniform ONNX tay ~50 dòng letterbox+NMS (`uniform_engine.py:120-162`) vs `YOLO()` 5 dòng trong plan. `letterbox()` chết cùng khi migrate (`image.py:84`).
15. Dead code xác nhận 0 caller: `decode_kiosk_frame` (`image_service.py:37`), `resize_max_width` + `scale_boxes_back` + `letterbox` (`image.py:60,71,84`). `face_service.extract_best/active_count/gallery_version_bump` (`face_service.py:19,27,31`) 0 caller ngoài wrapper. `CHALLENGE` FE (`kiosk-decisions.ts:72,101`, `page.tsx:225`) là dead branch — server map CHALLENGE→VERIFYING (`service.py:94`), FE không bao giờ nhận `"CHALLENGE"`. DB pool Supabase Free 5/5 (`database.py:50-52`).

## 5. Sources

- `backend/src/detect_ai/recognition/pipeline.py:34-46,66-196,203-229`
- `backend/src/detect_ai/recognition/config.py:32-71,85-166`
- `backend/src/detect_ai/recognition/face_engine.py:21-26,35-135,141-159`
- `backend/src/detect_ai/recognition/gallery.py:38-62,113-129,223-263`
- `backend/src/detect_ai/recognition/tracks.py:26-91`
- `backend/src/detect_ai/recognition/liveness.py:59-84,87-123,126-213`
- `backend/src/detect_ai/recognition/uniform_engine.py:80-162,175-224`
- `backend/src/detect_ai/recognition/service.py:31-212`
- `backend/src/detect_ai/recognition/enroll.py:16-72`
- `backend/src/detect_ai/recognition/image.py:27-57,84-94`
- `backend/src/detect_ai/api/routes_kiosk.py:39-62,72-99,102-169,172-285`
- `backend/src/detect_ai/api/routes_kiosk_ws.py:39-62,65-210`
- `backend/src/detect_ai/models/face.py:9-53`
- `backend/src/detect_ai/models/attendance_v2.py:23-80`
- `backend/src/detect_ai/services/image_service.py:20-60,104-245` (`decode_kiosk_frame:37` dead)
- `backend/src/detect_ai/recognition/image.py:60-95` (`resize/scale/letterbox` dead)
- `backend/src/detect_ai/services/face_service.py:19-31` (3 hàm dead)
- `backend/src/detect_ai/core/database.py:44-81` (pool, WAL, init_db)
- `backend/src/detect_ai/services/settings_repo.py:48-64` (min_gap cache 30s)
- `backend/src/detect_ai/core/supabase.py:13-25` (bucket snapshots đã bỏ legacy; snapshot nay local `/static/storage`, mount `main.py:116-117`)
- `backend/sql/04_face_tables.sql`, `05_recognition_v2.sql`, `06_pgvector_gallery.sql`, `08_attendance_snapshots.sql`
- `backend/.env.example:35-73`, `backend/src/detect_ai/core/config.py:38-61`
- `backend/src/detect_ai/main.py:27-93` (lifespan, pools, warmup)
- `backend/src/detect_ai/services/face_service.py:1-32`
- `frontend/app/teacher/classes/[id]/kiosk/page.tsx:43-104,129-293,342-539`
- `frontend/lib/face-detector.ts:1-51,53-181`
- `frontend/lib/kiosk-decisions.ts:8-108`
- `frontend/lib/api.ts:543-614`
- `backend/tests/test_recognition_v2.py:34-277`
- `docs/RECOGNITION_V2_PLAN.md:1-146`

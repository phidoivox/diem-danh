# Recognition v2 — Kế Hoạch Làm Lại (Hybrid Client-Server, Library-First)

## 1. Mục tiêu

Kiosk cần: Face ID + chống giả mạo + check đồng phục, video trực tiếp cửa lớp.

Vấn đề cũ:
- Server vẽ box trễ 200–500ms → giật.
- `IoUTracker` tay mất ID khi quay đầu/che nhẹ → vote per-sid sống qua đổi ID.
- `uniform_engine.py` letterbox + NMS + `ort.InferenceSession` tay (~100 dòng).
- `liveness.py` dùng `Liveness` cũ + MiniFAS tay. 2 bản ONNX công khai output hằng. InsightFace 2.0 đổi API hẳn.

Chốt:
- Kiến trúc Hybrid Client-Server.
- Liveness model ONNX server.
- Tracking: chốt IoU (`recognition/tracks.py`), xóa yêu cầu ByteTrack.
  Lý do: kiosk cửa lớp max 3 mặt, ByteTrack+Kalman overkill, lại trả
  tracker_id=-1 phải fallback số ngẫu nhiên làm vỡ vote. IoU greedy + TTL
  2s đủ ổn định, ~50 dòng, không thêm dependency. Vote gắn per-sid nên
  đổi track ID không reset CONFIRMED.

## 2. Kiến trúc

```
Camera kiosk
 │ 60 FPS local
 ▼
MediaPipe FaceDetector → vẽ box canvas (0ms)
 │ JPEG 480px q0.6, 1 in-flight, ~400ms qua WS
 ▼
routes_kiosk_ws.py (queue latest-only maxsize=1, drop cũ)
 ├─ InsightFace.get → embedding + liveness cùng lúc
 ├─ ByteTrackTracker.update → track_id
 ├─ Gallery matcher → top1/top2 margin
 ├─ Pipeline vote N/W → PROVISIONAL/CONFIRMED/SPOOF/CHALLENGE/UNKNOWN/LOWQ/REJECTED
 ├─ YOLO uniform run-once khi vote >= N-1 → ok/violation/unknown
 └─ service upsert check-in/check-out (max 2 lượt/tiết)
 │ JSON {track_id,bbox,student_id,decision,uniform_status,infer_ms}
 ▼
matchServerIdentities() ghép nhãn server (trễ 200–400ms) vào box 60 FPS
```

Hot-path sau xong: `ByteTrackTracker -> InsightFace.get -> YOLO run-once`.

## 3. Xác thực docs

- `sv.ByteTrack` chết: deprecated 0.28, xóa 0.31. Dùng `trackers.ByteTrackTracker`. Method `update(detections, frame=None)`, không `update_with_detections`. Nguồn: `/roboflow/supervision` trackers.md, deprecated.md + `trackers.roboflow.com/latest`, PyPI trackers 2.6.0.
- `trackers` cần `supervision>=0.26.1`, `numpy>=2.0.2`, `scipy`, `opencv-python`, Python>=3.10. Dự án Python 3.12 → tương thích.
- `YOLO("yolo26n.pt")` + `YOLO("yolo26n.onnx")` cùng API. `model(img, verbose=False)[0]` → `sv.Detections.from_ultralytics`. NMS nội bộ. `nms=False` = end-to-end `(N,300,6)`. Nguồn: `/ultralytics/ultralytics` onnx.md, yolo26.md.
- Prod YOLO: export OpenVINO, auto LATENCY mode batch=1, nhanh hơn `.pt` CPU 2–3x Intel.
- `sv.box_iou_batch` chưa snippet xác nhận → giữ `_iou` tay tạm, không thay mù.
- InsightFace 2.0: bỏ `from insightface.addons.liveness import Liveness`. Chuẩn `FaceAnalysis(addons=["liveness"], liveness_mode="observe", liveness_threshold=0.8)`, đọc `face.liveness.status/is_live/live_score`. Model tự tải `~/.insightface/addons/liveness.onnx`, SHA-check. Bắt buộc `observe`, cấm `normal` (normal cắt embedding khi fake → vỡ match/vote). Nguồn: insightface.ai/guides/rgb-liveness, PyPI 2.0.
- BlazeFace short-range ultrafast, mobile GPU-first, <2m đúng cửa lớp. Sparse nhanh hơn ~30% CPU XNNPACK.
- WS latest-only + 1 in-flight + drop cũ khớp WebSocketRT, SkellyCam, ASCILINE.

## 4. Thay đổi theo file

### `backend/pyproject.toml`
- Thêm `trackers` (+ kéo `supervision>=0.26.1`).
- Giữ `ultralytics>=8.3`, `insightface>=0.7`, `onnxruntime>=1.18`.

### `recognition/config.py`
- Thêm: `track_activation_threshold=0.25`, `lost_track_buffer=30`, `minimum_matching_threshold=0.8`, `minimum_consecutive_frames=1` (ID ngay frame đầu, không trễ vote).
- Weights YOLO: `best.pt` > `uniform_yolo26.pt` > `.onnx` > fallback.
- Xóa config `minifas_model`.

### `recognition/tracks.py` — chốt IoU, không ByteTrack
- Giữ `IoUTracker`, `_iou`, greedy, TTL 2s (`tracks.py` hiện tại).
- Vote gắn per-sid (`votes_by_sid` trong `KioskSession.process`) nên đổi
  track ID không reset CONFIRMED. Tracker chỉ phục vụ vẽ box; `done`
  scope in/out (checkout → `done_students.discard(sid)` trong service).

### `recognition/face_engine.py` — gộp liveness vào detect
```python
FaceAnalysis(name=want, allowed_modules=["detection","recognition"],
  addons=["liveness"], liveness_mode="observe", liveness_threshold=0.8)
```
- `Face` thêm `live_score: float | None`, `live_status: str | None` từ `face.liveness`.
- Dùng `face.normed_embedding` sẵn L2. `ctx_id` qua `_providers.ctx_id_for`.
- Warmup startup: 1 frame đen qua `app.get` + 1 frame qua YOLO.

### `recognition/liveness.py` — gọn
- Xóa MiniFAS tay (resolve/crop/softmax).
- Giữ fail-closed: thiếu addon → `REJECTED`.
- Map `live_score` từ `Face`, stateless. EMA/streak ở pipeline.

### `recognition/uniform_engine.py` — xóa ~100 dòng
- Xóa `_predict_onnx`, letterbox tay, `_nms`, `ort.InferenceSession`.
- Mới:
```python
self.model = YOLO(str(path))
r = self.model(img, verbose=False, conf=cfg.uniform_conf,
  imgsz=cfg.uniform_imgsz, max_det=20, classes=[0,1,2])[0]
det = sv.Detections.from_ultralytics(r)
```
- `verbose=False` bắt buộc (khỏi spam log mỗi frame).
- Lọc: `persons = det[det.class_id == 0]`.
- `uniform_for_face` giữ logic person-chứa-face + áo trong person. Giữ `_iou` tay tạm:
```python
# ponytail: thay bằng sv IoU batch khi docs rõ, upgrade path: box_iou_batch
```
- 1 API cho `.pt` + `.onnx`.

### `recognition/image.py`
- Xóa `letterbox` (chết cùng ONNX tay).
- Giữ `decode_frame` cv2 fast-path kiosk + `decode_strict` Pillow EXIF/bomb-guard enroll. Không thư viện thay được.

### `recognition/_providers.py` — giữ
- Giữ chain `Tensorrt>CUDA>DML>CoreML>OpenVINO>CPU`.
- Thêm `apply_cpu_threads` lúc startup, khỏi asyncio đói.
- Giữ `_pick_imgsz`: CPU yếu 320, thường 384, GPU 640.

### `recognition/pipeline.py`
- Signature tracker mới `update(boxes, scores, now)`.
- Liveness ưu tiên `face.live_score`, lazy chỉ candidate accept.
- Uniform run-once khi `vote >= N-1`, cache `uniform_done[sid]`. Máy trạng thái giữ nguyên.

### `service.py`, `routes_kiosk_ws.py` — giữ
- 2 lượt/tiết, `MIN_CHECKOUT_GAP_MINUTES`, proof crop, latest-only, `next_interval_ms/next_width` theo `infer_ms`.
- Snapshot vẽ dùng `sv.BoxAnnotator` + `sv.LabelAnnotator`, bỏ cv2 tay.

### Frontend — giữ
- `face-detector.ts`: `FilesetResolver`, `createFromOptions`, `detectForVideo` sync mỗi rAF, `matchServerIdentities` IoU.
- `kiosk/page.tsx`: canvas overlay, màu xanh lá CHECKED_IN / xanh dương VERIFYING / đỏ SPOOF / vàng UNKNOWN+violation, WS 1 in-flight, cooldown 12s, chime khi chốt.

## 5. Giữ / xóa

Giữ (nghiệp vụ): voting pipeline, gallery margin, attendance rules, MediaPipe client, decode 2 đường, provider chain.
Xóa: `IoUTracker`, ONNX/NMS/letterbox tay, MiniFAS tay. ~200 dòng.

## 6. Steps (thứ tự nghiêm ngặt, tránh vỡ pipeline)

1. Deps `trackers` vào `pyproject.toml`. Lý do: `pipeline` phụ thuộc signature mới.
2. Viết lại `tracks.py` bằng `ByteTrackTracker`.
3. Chuyển `uniform_engine.py` sang `YOLO()` + `from_ultralytics`. Xóa đường ONNX tay.
4. Sửa `face_engine.py` addons observe, sau đó gọn `liveness.py`. Pipeline đọc `face.live_score` trực tiếp.
5. Kiểm WS + kiosk 60 FPS.

## 7. Verify

- `pytest backend/tests/test_recognition_v2.py -v`: ID ổn định, CONFIRMED + uniform hook 1 lần, REJECTED fail-closed, spoof streak, margin match.
- Test WS: chuỗi frame mẫu → JSON `faces/checked_in/infer_ms/dropped`.
- `npx tsc --noEmit` frontend.
- E2E: box mượt, tên ghép đúng, chime khi chốt.
- Timeline dự kiến: box T+16ms, PROVISIONAL T+400ms+infer, CONFIRMED CPU 1.0–1.6s / GPU 0.2–0.4s. YOLO +15–60ms 1 lần/người/tiết.

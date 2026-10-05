from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import numpy as np
from loguru import logger

BACKEND_DIR = Path(__file__).resolve().parents[3]


def _load_model(path: Path):
    from ultralytics import YOLO

    return YOLO(str(path))


def _predict_boxes(model, img: np.ndarray, conf: float, imgsz: int):
    r = model.predict(img, conf=conf, imgsz=imgsz, verbose=False)[0]
    names = model.names
    n = len(r.boxes) if r.boxes is not None else 0
    out = []
    for i in range(n):
        cls = int(r.boxes.cls[i])
        out.append({
            "cls": names.get(cls, str(cls)),
            "conf": round(float(r.boxes.conf[i]), 3),
            "xyxy": np.array(r.boxes.xyxy[i].tolist(), dtype=np.float32),
        })
    return out


from detect_ai.modules.recognition.infrastructure.geometry import iou as _iou


def _parity(b_pt: list[dict], b_onnx: list[dict], iou_thr: float = 0.5) -> tuple[bool, str]:
    """So parity theo IoU từng box (greedy match cùng class), không chỉ so tên class.

    Bản cũ `sorted(class) == sorted(class)` cho parity giả khi box lệch/conf trôi.
    """
    if len(b_pt) != len(b_onnx):
        return False, f"số box lệch ({len(b_pt)} vs {len(b_onnx)})"
    used = [False] * len(b_onnx)
    max_conf_drift = 0.0
    for p in b_pt:
        best, best_j = 0.0, -1
        for j, o in enumerate(b_onnx):
            if used[j] or o["cls"] != p["cls"]:
                continue
            v = _iou(p["xyxy"], o["xyxy"])
            if v > best:
                best, best_j = v, j
        if best < iou_thr:
            return False, f"box '{p['cls']}' không khớp IoU (tốt nhất {best:.2f})"
        used[best_j] = True
        max_conf_drift = max(max_conf_drift, abs(b_onnx[best_j]["conf"] - p["conf"]))
    return True, f"khớp {len(b_pt)} box, trôi conf ≤ {max_conf_drift:.3f}"


def bench(pt: Path, onnx: Path, imgs: list[Path], conf: float, imgsz: int, repeats: int) -> int:
    m_pt = _load_model(pt)
    m_onnx = _load_model(onnx)
    sample = np.zeros((384, 640, 3), np.uint8)
    for m in (m_pt, m_onnx):  # warmup ngoài giờ đo
        m.predict(sample, conf=conf, imgsz=imgsz, verbose=False)

    print(f"| ảnh | .pt boxes | .onnx boxes | parity (IoU≥0.5) |")
    print(f"|---|---|---|---|")
    mismatches = 0
    for img_path in imgs:
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"| {img_path.name} | đọc lỗi, bỏ qua | | |")
            continue
        b_pt = _predict_boxes(m_pt, img, conf, imgsz)
        b_onnx = _predict_boxes(m_onnx, img, conf, imgsz)
        ok, detail = _parity(b_pt, b_onnx)
        mismatches += 0 if ok else 1
        print(f"| {img_path.name} | {len(b_pt)} | {len(b_onnx)} | {'✓ ' + detail if ok else '✗ ' + detail} |")

    def _time(m) -> float:
        t0 = time.perf_counter()
        for _ in range(repeats):
            m.predict(sample, conf=conf, imgsz=imgsz, verbose=False)
        return (time.perf_counter() - t0) / repeats * 1000

    t_pt = _time(m_pt)
    t_onnx = _time(m_onnx)
    print(f"\nLatency trung bình ({repeats} lần, ảnh 640x384): .pt={t_pt:.1f}ms, .onnx={t_onnx:.1f}ms")
    print(f"Parity: {len(imgs) - mismatches}/{len(imgs)} ảnh khớp box (IoU≥0.5) + số box + class.")
    return mismatches


def main() -> None:
    ap = argparse.ArgumentParser(description="So sánh parity .pt vs .onnx + đo latency.")
    ap.add_argument("--pt", default=str(BACKEND_DIR / "yolo26n.pt"))
    ap.add_argument("--onnx", default=str(BACKEND_DIR / "data" / "weights" / "yolo26n.onnx"))
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--imgsz", type=int, default=384)
    ap.add_argument("--repeats", type=int, default=20)
    ap.add_argument("--max-imgs", type=int, default=5)
    args = ap.parse_args()

    img_dirs = [BACKEND_DIR / "data" / "faces", BACKEND_DIR / "data" / "snapshots"]
    imgs: list[Path] = []
    for d in img_dirs:
        if d.exists():
            imgs += sorted(p for p in d.glob("*.jpg") if p.is_file())[: args.max_imgs]
        if len(imgs) >= args.max_imgs:
            break
    imgs = imgs[: args.max_imgs]
    if not imgs:
        raise FileNotFoundError("Không tìm thấy ảnh mẫu trong data/faces hay data/snapshots.")
    rc = bench(Path(args.pt), Path(args.onnx), imgs, args.conf, args.imgsz, args.repeats)
    if rc:
        logger.warning(f"Có {rc} ảnh lệch parity — xem bảng trên trước khi triển khai.")
    else:
        logger.info("Parity OK trên toàn bộ ảnh mẫu.")


if __name__ == "__main__":
    main()

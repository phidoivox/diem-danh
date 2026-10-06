from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

BACKEND_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BACKEND_DIR / "data"
DEFAULT_OUT = DATA_DIR / "weights" / "yolo26n.onnx"

# Nguồn .pt: ưu tiên bản trong backend/, rồi tới bản ở gốc repo.
CANDIDATE_WEIGHTS = [
    BACKEND_DIR / "yolo26n.pt",
    BACKEND_DIR.parent / "yolo26n.pt",
]


def resolve_weights(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.exists():
            raise FileNotFoundError(f"weights không tồn tại: {p}")
        return p
    for p in CANDIDATE_WEIGHTS:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Không tìm thấy yolo26n.pt trong backend/ hay gốc repo. "
        "Truyền --weights <đường dẫn> explicitly."
    )


def export_onnx(weights: Path, out: Path, imgsz: int = 384, opset: int = 17) -> Path:
    """Export yolo26n.pt sang ONNX FP32 (static shape, simplify).

    opset=17: tương thích rộng nhất với onnxruntime trên mọi nền tảng
    (CUDA/TensorRT/DirectML/CoreML/OpenVINO/CPU), khỏi thử-sai runtime.
    """
    from ultralytics import YOLO

    out.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights))
    exported = model.export(
        format="onnx",
        imgsz=imgsz,
        opset=opset,
        simplify=True,
        dynamic=False,
        half=False,
    )
    got = Path(str(exported))
    if got.resolve() != out.resolve():
        # Ultralytics không tôn trọng tên file out -> dời file thay vì đọc/ghi tay.
        got.replace(out)
    logger.info(f"Đã export {weights.name} -> {out} (imgsz={imgsz}, opset={opset}, FP32)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Export yolo26n.pt sang ONNX FP32.")
    ap.add_argument("--weights", default=None, help="Đường dẫn yolo26n.pt (mặc định tự tìm).")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="Đường dẫn .onnx đầu ra.")
    ap.add_argument("--imgsz", type=int, default=384, help="Kích thước export (mặc định 384).")
    ap.add_argument("--opset", type=int, default=17, help="ONNX opset (mặc định 17, tương thích rộng nhất).")
    args = ap.parse_args()
    weights = resolve_weights(args.weights)
    export_onnx(weights, Path(args.out), imgsz=args.imgsz, opset=args.opset)


if __name__ == "__main__":
    main()

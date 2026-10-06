from __future__ import annotations

"""Runtime helpers (vendor từ ai/ort_runtime + ai/yolo_runtime cũ, đã xóa).

Một nguồn sự thật cho onnxruntime providers + chọn cấu hình YOLO theo phần cứng.
Không import nặng ở top-level (onnxruntime/torch lazy trong hàm).
"""

import os
import platform
from dataclasses import dataclass, field
from functools import lru_cache


@lru_cache(maxsize=1)
def available_providers() -> tuple[str, ...]:
    try:
        import onnxruntime

        return tuple(onnxruntime.get_available_providers())
    except Exception:  # noqa: BLE001
        return ("CPUExecutionProvider",)


PROVIDER_PRIORITY = (
    "TensorrtExecutionProvider",
    "CUDAExecutionProvider",
    "DmlExecutionProvider",
    "CoreMLExecutionProvider",
    "OpenVINOExecutionProvider",
    "CPUExecutionProvider",
)

PROVIDER_ALIASES = {
    "cpu": "CPUExecutionProvider",
    "cuda": "CUDAExecutionProvider",
    "tensorrt": "TensorrtExecutionProvider",
    "dml": "DmlExecutionProvider",
    "directml": "DmlExecutionProvider",
    "coreml": "CoreMLExecutionProvider",
    "openvino": "OpenVINOExecutionProvider",
}


def pick_providers(explicit: str = "auto") -> tuple[list[str], bool]:
    """Trả (provider_chain, has_gpu). Ép provider không có sẵn -> rớt về auto."""
    avail = set(available_providers())
    want = (explicit or "auto").strip().lower()
    if want not in ("", "auto"):
        name = PROVIDER_ALIASES.get(want, explicit)
        if name in avail:
            chain = [name] if name == "CPUExecutionProvider" else [name, "CPUExecutionProvider"]
            return chain, name != "CPUExecutionProvider"
    ordered = [p for p in PROVIDER_PRIORITY if p in avail] or ["CPUExecutionProvider"]
    return ordered, ordered[0] != "CPUExecutionProvider"


def ctx_id_for(has_gpu: bool) -> int:
    """ctx_id=0 là GPU0 (InsightFace); máy CPU-only phải là -1."""
    return 0 if has_gpu else -1


@dataclass
class YoloRuntime:
    """Cấu hình inference YOLO đã tự nhận diện theo phần cứng."""

    providers: list[str] = field(default_factory=lambda: ["CPUExecutionProvider"])
    imgsz: int = 384
    threads: int = 2
    has_gpu: bool = False

    @property
    def provider(self) -> str:
        return self.providers[0] if self.providers else "CPUExecutionProvider"


def _pick_imgsz(explicit: int, cpu_count: int, has_gpu: bool) -> int:
    if explicit and explicit > 0:
        return int(explicit)
    if has_gpu:
        return 640
    if cpu_count >= 8:
        return 480
    if cpu_count <= 2:
        return 320
    return 384


def _pick_threads(explicit: int, cpu_count: int) -> int:
    if explicit and explicit > 0:
        return max(1, int(explicit))
    return min(4, max(1, (cpu_count or 4) // 2))


def detect_runtime(explicit_provider: str = "auto", explicit_imgsz: int = 0,
                   explicit_threads: int = 0, cpu_count: int | None = None) -> YoloRuntime:
    ncpu = cpu_count or os.cpu_count() or 4
    providers, has_gpu = pick_providers(explicit_provider)
    return YoloRuntime(
        providers=providers,
        imgsz=_pick_imgsz(explicit_imgsz, ncpu, has_gpu),
        threads=_pick_threads(explicit_threads, ncpu),
        has_gpu=has_gpu,
    )


def apply_cpu_threads(threads: int) -> None:
    """Giới hạn thread CPU để YOLO/ONNX không giành hết CPU với asyncio."""
    threads = max(1, int(threads))
    os.environ.setdefault("OMP_NUM_THREADS", str(threads))
    os.environ.setdefault("MKL_NUM_THREADS", str(threads))
    try:
        import torch

        torch.set_num_threads(threads)
    except Exception:
        pass


def describe() -> str:
    r = detect_runtime()
    return (f"platform={platform.system()} cpu={os.cpu_count()} "
            f"provider={r.provider} imgsz={r.imgsz} threads={r.threads}")

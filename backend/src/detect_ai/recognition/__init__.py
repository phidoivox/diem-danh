"""Recognition v2: face + uniform rebuilt from scratch (parallel with legacy ai/).

MediaPipe frontend giữ nguyên. Backend mới với:
- config tập trung + auto-tune bằng đo thật
- gallery multi-prototype + margin (không mean-pool)
- liveness fail-closed + challenge hook
- uniform ONNX run-once lúc check-in
- tracker IoU nhẹ (bỏ ByteTrack khỏi đường face)
- pipeline + service single-source cho HTTP/WS
"""
from detect_ai.modules.recognition.infrastructure.config import RecognitionConfig, get_config

__all__ = ["RecognitionConfig", "get_config"]

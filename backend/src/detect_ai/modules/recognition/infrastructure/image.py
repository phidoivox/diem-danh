from __future__ import annotations

"""1 cổng decode ảnh duy nhất cho recognition v2.

Gộp 2 đường cũ (Pillow EXIF nghiêm + cv2 fast-path kiosk) với quy ước rõ:
- enroll/avatar: dùng decode_strict (Pillow, xử lý EXIF, chống decompression-bomb).
- kiosk stream: dùng decode_frame (cv2, nhanh ~2x, không EXIF vì camera landscape).
Output luôn BGR uint8 (quy ước OpenCV).
"""

from io import BytesIO

import numpy as np
from PIL import Image, ImageOps

MAX_IMAGE_PIXELS = 12_000_000
try:
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
except Exception:
    pass


class ImageDecodeError(ValueError):
    pass


def decode_strict(content: bytes) -> np.ndarray:
    """Decode nghiêm cho enroll/avatar (EXIF + validate)."""
    if not content:
        raise ImageDecodeError("File ảnh rỗng")
    try:
        with Image.open(BytesIO(content)) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            if im.width * im.height > MAX_IMAGE_PIXELS:
                raise ImageDecodeError("ảnh quá lớn")
            rgb = np.asarray(im, dtype=np.uint8)
    except ImageDecodeError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ImageDecodeError(f"File ảnh lỗi hoặc không đọc được: {e}")
    return rgb[:, :, ::-1].copy()


def decode_frame(content: bytes, max_width: int = 480) -> np.ndarray:
    """Fast-path cho kiosk (cv2.imdecode + resize). Không EXIF."""
    import cv2

    if not content:
        raise ImageDecodeError("Frame ảnh rỗng")
    arr = np.frombuffer(content, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        raise ImageDecodeError("Frame ảnh không đọc được")
    if max_width > 0 and img.shape[1] > max_width:
        s = max_width / float(img.shape[1])
        img = cv2.resize(img, (max_width, max(1, int(img.shape[0] * s))), interpolation=cv2.INTER_LINEAR)
    return img


def encode_jpeg(img_bgr: np.ndarray, quality: int = 60) -> bytes:
    rgb = img_bgr[:, :, ::-1]
    buf = BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=int(quality))
    return buf.getvalue()

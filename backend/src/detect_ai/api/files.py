from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np
from fastapi import HTTPException, UploadFile


async def decode_upload(photo: UploadFile) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(await photo.read(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(422, "anh loi")
    return img


def safe_file(base: Path, name: str) -> Path:
    # chan path traversal: chi file nam trong dir cho phep
    p = (base / name).resolve()
    if base.resolve() not in p.parents or not p.is_file():
        raise HTTPException(404, "not found")
    return p

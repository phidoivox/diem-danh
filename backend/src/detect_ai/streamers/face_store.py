from __future__ import annotations

import json
from typing import Any, Optional
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from detect_ai.shared.kernel.database import Session
from detect_ai.modules.identity.infrastructure.models import User, StudentProfile

try:
    from detect_ai.modules.recognition.infrastructure.bench.face_recognizer import FaceIndex
except ImportError:  # faiss absent in test env
    FaceIndex = None  # type: ignore[assignment,misc]

# Cache embedding + index trong RAM: khong query DB moi connection.
embs = np.zeros((0, 512), np.float32)
meta: list[dict] = []
index = FaceIndex() if FaceIndex is not None else None


def _rebuild_index() -> None:
    global index
    if FaceIndex is None:
        index = None
        return
    if index is None:
        index = FaceIndex()
    index.rebuild(embs)

def decode_embedding(raw: Any) -> Optional[np.ndarray]:
    """Decode raw embedding (JSON list float, bytes float32, or string) to (512,) float32."""
    if raw is None:
        return None
    try:
        if isinstance(raw, (bytes, bytearray, memoryview)):
            arr = np.frombuffer(raw, dtype=np.float32)
        elif isinstance(raw, list):
            arr = np.array(raw, dtype=np.float32)
        elif isinstance(raw, str):
            raw_str = raw.strip()
            if not raw_str:
                return None
            if raw_str.startswith("[") and raw_str.endswith("]"):
                try:
                    arr = np.array(json.loads(raw_str), dtype=np.float32)
                except Exception:
                    arr = np.fromstring(raw_str[1:-1], sep=",", dtype=np.float32)
            else:
                arr = np.fromstring(raw_str, sep=",", dtype=np.float32)
        elif isinstance(raw, np.ndarray):
            arr = raw.astype(np.float32).flatten()
        else:
            arr = np.array(raw, dtype=np.float32)

        if arr.size == 0:
            return None

        # Standardize to 512 dimensions for FaceIndex
        if len(arr) == 512:
            return arr.astype(np.float32)
        elif len(arr) < 512:
            padded = np.zeros(512, dtype=np.float32)
            padded[:len(arr)] = arr
            return padded
        else:
            return arr[:512].astype(np.float32)
    except Exception:
        return None

async def _load_from_session(s: AsyncSession) -> None:
    global embs, meta
    stmt = (
        select(
            StudentProfile.face_embedding,
            User.user_code,
            User.full_name,
            StudentProfile.class_name,
        )
        .join(User, StudentProfile.user_id == User.id)
        .where(
            User.is_active == True,
            User.deleted_at.is_(None),
            StudentProfile.face_embedding.isnot(None),
        )
    )
    rows = (await s.execute(stmt)).all()

    valid_embs: list[np.ndarray] = []
    valid_meta: list[dict] = []

    for raw_emb, u_code, full_name, cls_name in rows:
        vec = decode_embedding(raw_emb)
        if vec is not None:
            valid_embs.append(vec)
            valid_meta.append({
                "code": u_code,
                "name": full_name,
                "class_name": cls_name or "",
            })

    if valid_embs:
        embs = np.stack(valid_embs).astype(np.float32)
    else:
        embs = np.zeros((0, 512), np.float32)
    meta = valid_meta
    _rebuild_index()

async def reload(session: Optional[AsyncSession] = None) -> None:
    """Reload face embeddings and rebuild index safely."""
    if session is not None:
        await _load_from_session(session)
    else:
        async with Session() as s:
            await _load_from_session(s)

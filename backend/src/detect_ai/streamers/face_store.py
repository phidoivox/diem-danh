from __future__ import annotations
import numpy as np
from sqlalchemy import select
from ..ai.face_recognizer import FaceIndex
from ..core.database import Session
from ..models.student import Student

# Cache embedding + faiss index trong RAM: khong query DB moi connection.
embs = np.zeros((0, 512), np.float32)
meta: list[dict] = []
index = FaceIndex()

async def reload() -> None:
    global embs, meta
    async with Session() as s:
        rows = (await s.execute(select(Student))).scalars().all()
        embs = np.stack([np.frombuffer(r.embedding, np.float32) for r in rows]) if rows else np.zeros((0, 512), np.float32)
        meta = [{"code": r.code, "name": r.name, "class_name": r.class_name} for r in rows]
    index.rebuild(embs)

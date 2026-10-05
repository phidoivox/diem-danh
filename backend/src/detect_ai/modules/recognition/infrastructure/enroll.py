from __future__ import annotations

"""Enroll v2: trích + lưu embedding (dùng chung admin upload và backfill).

Khác face_service cũ: dùng FaceEngine DI (mock được), bump gallery version
để kiosk thấy ngay (không chờ TTL 5 phút), giữ max 5 vector/SV.
"""

from sqlalchemy import select

from .models import FaceEmbedding
from . import liveness as live_mod
try:
    from .face_engine import FaceEngine, embedding_to_json, quality
except ImportError:
    from detect_ai.recognition.face_engine import FaceEngine, embedding_to_json, quality
from .gallery import bump_version

MAX_ACTIVE_PER_USER = 5
MIN_ENROLL_QUALITY = 0.40


class EnrollError(ValueError):
    pass


def extract_best(img_bgr, engine: FaceEngine | None = None):
    eng = engine or FaceEngine(max_faces=1, max_width=960)
    faces = eng.detect(img_bgr)
    if not faces:
        raise EnrollError("Không tìm thấy khuôn mặt trong ảnh.")
    face = faces[0]
    q = quality(face, img_bgr)
    if q < MIN_ENROLL_QUALITY:
        raise EnrollError(f"Ảnh mờ/khuất (quality={q:.2f}), hãy chụp ảnh rõ chính diện.")
    vd = live_mod.check_live(img_bgr, face.kps)
    if vd.verdict == "spoof":
        raise EnrollError(f"Ảnh không qua kiểm tra người thật (liveness={vd.score:.2f}).")
    if vd.verdict == "no_model":
        raise EnrollError("Thiếu model liveness, không thể xác thực ảnh thật.")
    return face, q, vd.score


async def enroll_image(db, user_id: int, img_bgr, source: str = "avatar",
                       engine: FaceEngine | None = None) -> FaceEmbedding:
    face, q, _live = extract_best(img_bgr, engine)
    stmt = (
        select(FaceEmbedding)
        .where(FaceEmbedding.user_id == user_id, FaceEmbedding.is_active == True)  # noqa: E712
        .order_by(FaceEmbedding.id.desc())
    )
    actives = (await db.execute(stmt)).scalars().all()
    for old in actives[MAX_ACTIVE_PER_USER - 1:]:
        old.is_active = False
    row = FaceEmbedding(user_id=user_id, embedding=embedding_to_json(face.embedding),
                        quality=float(q), source=source, is_active=True)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    # Gallery cache key theo class -> bump mọi lớp chứa SV để kiosk thấy ngay.
    # Vector chỉ ghi 1 cột embedding JSON (tìm pgvector qua expression index).
    try:
        from detect_ai.models.academic import ClassStudent
        from .gallery import _is_postgres, bump_db_version, bump_version

        cids = (await db.execute(select(ClassStudent.class_id).where(
            ClassStudent.student_id == user_id))).scalars().all()
        for cid in cids:
            bump_version(int(cid))  # RAM cục bộ thấy ngay
            if _is_postgres(db):
                await bump_db_version(db, int(cid))  # worker khác thấy ngay
    except Exception:  # noqa: BLE001
        pass
    return row


async def active_count(db, user_id: int) -> int:
    from sqlalchemy import func

    stmt = select(func.count()).select_from(FaceEmbedding).where(
        FaceEmbedding.user_id == user_id, FaceEmbedding.is_active == True  # noqa: E712
    )
    return int((await db.execute(stmt)).scalar_one() or 0)

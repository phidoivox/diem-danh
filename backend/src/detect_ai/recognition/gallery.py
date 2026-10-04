from __future__ import annotations

"""Gallery v2: multi-prototype + margin (không mean-pool như code cũ).

Code cũ (ai/face_gallery.py): mỗi SV trộn hết vector thành 1 centroid.
Vấn đề: chính diện + nghiêng trộn vào nhau thành vector mờ -> miss + nhầm.

Mới: giữ hết vector/SV, match top1/top2 + margin:
- accept: top1 >= thr VÀ (top1 - top2) >= margin_min
- unsure: top1 trong [unsure_low, thr) hoặc margin nhỏ
- unknown: còn lại

Lớp 30-100 SV: matrix RAM <1ms, chưa cần FAISS/pgvector.
Cache versioned theo class (bump khi enroll) thay TTL mù 5 phút.
"""

import time
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import select, text

from ..models.academic import ClassStudent
from ..models.face import FaceEmbedding
from ..models.user import User
from .face_engine import json_to_array


@dataclass
class ProtoEntry:
    student_id: int
    user_code: str
    full_name: str
    vectors: list[np.ndarray]  # mỗi vector (512,) normalized


@dataclass
class Gallery:
    class_id: int
    version: int
    entries: list[ProtoEntry]
    matrix: np.ndarray = field(repr=False)  # (N_protos, 512)
    owner: np.ndarray = field(repr=False)  # (N_protos,) student_id
    loaded_at: float = 0.0

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def proto_count(self) -> int:
        return int(self.matrix.shape[0]) if self.matrix.size else 0


_cache: dict[int, tuple[float, int, Gallery]] = {}
_versions: dict[int, int] = {}


def bump_version(class_id: int) -> int:
    v = _versions.get(class_id, 0) + 1
    _versions[class_id] = v
    _cache.pop(class_id, None)
    return v


def current_version(class_id: int) -> int:
    return _versions.get(class_id, 0)


def _is_postgres(db) -> bool:
    """True khi chạy Postgres/pgvector (Supabase); SQLite dev trả False."""
    try:
        return db.get_bind().dialect.name == "postgresql"
    except Exception:
        return False


async def fetch_db_version(db, class_id: int) -> int | None:
    """Version gallery trong DB (None khi SQLite hoặc chưa có bảng)."""
    if not _is_postgres(db):
        return None
    try:
        row = await db.execute(
            text("SELECT version FROM gallery_versions WHERE class_id = :cid"),
            {"cid": class_id},
        )
        v = row.scalar_one_or_none()
        return int(v) if v is not None else 0
    except Exception:
        return None


async def bump_db_version(db, class_id: int) -> int | None:
    """Tăng version gallery trong DB (multi-worker cùng thấy). None khi SQLite."""
    if not _is_postgres(db):
        return None
    try:
        row = await db.execute(
            text("""INSERT INTO gallery_versions (class_id, version, updated_at)
                    VALUES (:cid, 1, now())
                    ON CONFLICT (class_id) DO UPDATE
                    SET version = gallery_versions.version + 1, updated_at = now()
                    RETURNING version"""),
            {"cid": class_id},
        )
        v = row.scalar_one()
        await db.commit()
        return int(v)
    except Exception:
        await db.rollback()
        return None


async def load_gallery(db, class_id: int, ttl_s: int = 300, force: bool = False) -> Gallery:
    # TTL trước version check: cache hit -> return, tránh 1 SELECT version/frame.
    now = time.monotonic()
    hit = _cache.get(class_id)
    if not force and hit and now - hit[0] < max(30, ttl_s):
        return hit[2]
    pg = _is_postgres(db)
    if pg and not force:
        db_ver = await fetch_db_version(db, class_id)
        ver = db_ver if db_ver is not None else current_version(class_id)
    else:
        ver = current_version(class_id)
    if pg:
        gal = await _load_postgres(db, class_id, ver if ver is not None else 0, now)
    else:
        gal = await _load_orm(db, class_id, ver, now)
    _cache[class_id] = (now, gal.version, gal)
    return gal


async def _load_postgres(db, class_id: int, ver: int, now: float) -> Gallery:
    """Nạp từ Postgres (1 cột embedding JSON duy nhất; tìm vector bằng expression index).
    Đọc cột embedding JSON; embedding_vec pgvector dự phòng chưa dùng."""
    try:
        rows = (await db.execute(
            text("""SELECT u.id, u.user_code, u.full_name, fe.embedding
                    FROM users u
                    JOIN class_students cs ON cs.student_id = u.id
                    JOIN face_embeddings fe ON fe.user_id = u.id
                    WHERE cs.class_id = :cid
                      AND u.is_active IS TRUE AND u.deleted_at IS NULL
                      AND fe.is_active IS TRUE"""),
            {"cid": class_id},
        )).all()
    except Exception:
        return await _load_orm(db, class_id, ver, now)
    per: dict[int, dict] = {}
    for uid, code, name, emb_json in rows:
        try:
            vec = json_to_array(emb_json)
        except Exception:  # noqa: BLE001
            continue
        slot = per.setdefault(int(uid), {"vecs": [], "code": code, "name": name})
        slot["vecs"].append(vec)
    return _build_gallery(class_id, ver, per, now)


async def _load_orm(db, class_id: int, ver: int, now: float) -> Gallery:
    """Nạp bằng ORM từ cột JSON (SQLite dev)."""
    stmt = (
        select(User, FaceEmbedding)
        .join(ClassStudent, ClassStudent.student_id == User.id)
        .join(FaceEmbedding, FaceEmbedding.user_id == User.id)
        .where(
            ClassStudent.class_id == class_id,
            User.is_active == True,  # noqa: E712
            User.deleted_at.is_(None),
            FaceEmbedding.is_active == True,  # noqa: E712
        )
    )
    rows = (await db.execute(stmt)).all()
    per: dict[int, dict] = {}
    for user, emb in rows:
        try:
            vec = json_to_array(emb.embedding)
        except Exception:  # noqa: BLE001
            continue
        slot = per.setdefault(user.id, {"vecs": [], "code": user.user_code, "name": user.full_name})
        slot["vecs"].append(vec)
    return _build_gallery(class_id, ver, per, now)


def _build_gallery(class_id: int, ver: int, per: dict, now: float) -> Gallery:
    entries: list[ProtoEntry] = []
    mats: list[np.ndarray] = []
    owners: list[int] = []
    for sid, slot in per.items():
        vecs = [np.asarray(v, dtype=np.float32).reshape(-1) for v in slot["vecs"]]
        # Chuẩn hóa lại từng vector (phòng DB cũ chưa normalize)
        normed = []
        for v in vecs:
            n = float(np.linalg.norm(v))
            normed.append((v / n).astype(np.float32) if n > 0 else v.astype(np.float32))
        if not normed:
            continue
        entries.append(ProtoEntry(sid, slot["code"], slot["name"], normed))
        for v in normed:
            mats.append(v)
            owners.append(sid)
    if mats:
        mat = np.stack(mats).astype(np.float32)
        owner = np.asarray(owners, dtype=np.int64)
    else:
        mat = np.zeros((0, 512), np.float32)
        owner = np.zeros((0,), np.int64)
    return Gallery(class_id=class_id, version=ver, entries=entries, matrix=mat, owner=owner, loaded_at=now)


def invalidate(class_id: int) -> None:
    _cache.pop(class_id, None)


@dataclass
class MatchResult:
    student_id: int | None
    score: float
    margin: float
    decision: str  # accept | unsure | unknown | empty
    runner_up: int | None = None
    runner_score: float = 0.0


def match_topk(emb: np.ndarray, gallery: Gallery, topk: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """Trả (scores_topk, student_ids_topk) theo proto (chưa gộp SV)."""
    v = np.asarray(emb, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v))
    if n > 0:
        v = (v / n).astype(np.float32)
    if gallery.proto_count == 0:
        return np.zeros((0,), np.float32), np.zeros((0,), np.int64)
    scores = gallery.matrix @ v  # (N_protos,)
    k = max(1, min(topk, len(scores)))
    idx = np.argpartition(-scores, k - 1)[:k]
    order = idx[np.argsort(-scores[idx])]
    return scores[order].astype(np.float32), gallery.owner[order]


def match(emb: np.ndarray, gallery: Gallery, threshold: float = 0.45,
          unsure_low: float = 0.35, margin_min: float = 0.05) -> MatchResult:
    """Match với margin chống nhầm 2 bạn giống nhau."""
    if len(gallery) == 0 or gallery.proto_count == 0:
        return MatchResult(None, 0.0, 0.0, "empty")
    scores, owners = match_topk(emb, gallery, topk=2)
    top1, sid1 = float(scores[0]), int(owners[0])
    if len(scores) > 1:
        top2, sid2 = float(scores[1]), int(owners[1])
        # Nếu top2 cùng SV với top1 -> tìm runner khác SV để tính margin thật.
        # Quét TOÀN gallery (không cap topk): 1 SV tối đa 5 proto nên runner có
        # thể ở hạng 6+, cap 5 cũ cho margin 0 -> unsure oan. Gallery lớp học
        # (~200 proto) argpartition full rẻ (~µs), không cần tiết kiệm ở đây.
        if sid2 == sid1 and gallery.proto_count > 2:
            scores2, owners2 = match_topk(emb, gallery, topk=gallery.proto_count)
            top2, sid2 = top1, sid1
            for s, o in zip(scores2[1:], owners2[1:]):
                if int(o) != sid1:
                    top2, sid2 = float(s), int(o)
                    break
    else:
        top2, sid2 = -1.0, None
    # Gộp: nếu top2 cùng người thì margin tính với người khác gần nhất
    margin = top1 - top2 if sid2 is None or sid2 != sid1 else 0.0
    if top1 >= threshold and margin >= margin_min:
        return MatchResult(sid1, top1, margin, "accept", sid2 if sid2 != sid1 else None, top2)
    if top1 >= unsure_low:
        return MatchResult(sid1, top1, margin, "unsure", sid2 if sid2 != sid1 else None, top2)
    return MatchResult(None, top1, margin, "unknown", None, top2)

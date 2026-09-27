from __future__ import annotations

"""Service single-source cho kiosk v2: 1 hàm upsert dùng chung HTTP + WS.

Quy tắc điểm danh (theo yêu cầu):
- Chỉ mở khi có tiết (gate theo ngày nằm ở routes, hàm này chỉ lo giới hạn lượt).
- Mỗi người tối đa 2 lượt/tiết: lần CONFIRMED đầu -> check-in (+ snapshot in),
  lần CONFIRMED sau (cách check-in >= min_gap) -> check-out (+ snapshot out),
  từ lần 3 trở đi -> bỏ qua, báo already_done.
- Quét trùng trong khoảng min_gap (đứng yên trước camera) -> bỏ qua lặng lẽ.
- GV sửa tay (is_manual_override) -> không cho kiosk auto ghi đè.
- FaceEvent chỉ log khi có transition thật (in/out/spoof), không log mỗi frame.

Giữ nguyên JSON response cũ (checked_in) + thêm checked_out/already_done,
frontend cũ không vỡ.
"""

from datetime import datetime, timezone
from typing import Callable, Iterable

import numpy as np
from loguru import logger
from sqlalchemy import select

from ..models.attendance_v2 import Attendance, AttendanceStatus
from ..models.face import FaceEvent
from .config import get_config
from .pipeline import FaceDecision
from .uniform_engine import UniformEngine, uniform_for_face

_uniform: UniformEngine | None = None

#: Khoảng cách tối thiểu giữa check-in và check-out (phút). Có setting
#: CHECKOUT_MIN_GAP_MINUTES trong DB để admin nhìn thấy, nhưng hot-path kiosk
#: (mỗi ~450ms) không query DB nên dùng hằng số này làm mặc định.
MIN_CHECKOUT_GAP_MINUTES = 5


def uniform_hook_factory() -> Callable[..., object] | None:
    """Lazy singleton UniformEngine: 1 predict/frame (pipeline `uniform_predict`).

    Dual-mode để caller cũ (routes truyền positional vào `run_uniform`) không vỡ:
    1 arg (img) -> UniformDetections | None; 2 args (bbox, img) -> (status, reasons, score).
    ponytail: tach 2 factory khi routes chuyen sang `uniform_predict=` ro rang; ceiling = 2 callables.
    """
    global _uniform
    try:
        cfg = get_config()
    except Exception:
        return None
    if _uniform is None:
        try:
            _uniform = UniformEngine(imgsz=cfg.uniform_imgsz, conf=cfg.uniform_conf,
                                     provider=cfg.uniform_provider)
        except Exception:
            return None
    eng = _uniform

    def _predict(img_or_bbox: np.ndarray, img_bgr: np.ndarray | None = None):
        if img_bgr is None:
            try:
                return eng.predict(img_or_bbox)
            except Exception:
                return None
        try:
            det = eng.predict(img_bgr)
            st, _reasons, sc = uniform_for_face(img_or_bbox, det, iou_thr=cfg.uniform_iou_thr)
            return st, _reasons, sc
        except Exception:
            return "unknown", [], 0.0

    return _predict


def _detect_uniform(img_bgr):
    """Detect đồng phục trên đúng frame check-in/out để vẽ khung làm bằng chứng.

    Chỉ gọi đúng lúc transition (tối đa 2 lần/người/tiết) nên 1 lần infer
    thêm không ảnh hưởng hot-path kiosk. Thiếu weights -> None (vẫn lưu
    ảnh + khung mặt + timestamp).
    """
    global _uniform
    try:
        cfg = get_config()
    except Exception:
        return None
    if _uniform is None:
        try:
            _uniform = UniformEngine(imgsz=cfg.uniform_imgsz, conf=cfg.uniform_conf,
                                     provider=cfg.uniform_provider)
        except Exception:
            return None
    try:
        return _uniform.predict(img_bgr)
    except Exception:
        return None


def to_legacy(decision: str) -> str:
    """Map decision v2 -> chuỗi cũ cho frontend hiện tại."""
    return {
        "CONFIRMED": "CHECKED_IN",
        "PROVISIONAL": "VERIFYING",
        "CHALLENGE": "VERIFYING",
        "SPOOF": "SPOOF",
        "UNKNOWN": "UNKNOWN",
        "LOWQ": "LOWQ",
        "REJECTED": "VERIFYING",
    }.get(decision, decision)


def _as_aware(dt: datetime | None) -> datetime | None:
    """SQLite trả datetime naive, Postgres trả aware -> chuẩn hóa về aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def commit_decisions(db, schedule_id: int, teacher_id: int,
                           decisions: Iterable[FaceDecision],
                           frame_bgr=None,
                           min_gap_minutes: int = MIN_CHECKOUT_GAP_MINUTES) -> dict:
    """Ghi Attendance + snapshot local + FaceEvent cho các CONFIRMED.

    Trả dict {"checked_in": [...], "checked_out": [...], "already_done": [...]}
    danh sách student_id. Giữ tương thích: caller cũ chỉ đọc checked_in.
    """
    from ..services import image_service as _img_svc

    now = datetime.now(timezone.utc)
    checked_in: list[int] = []
    checked_out: list[int] = []
    already_done: list[int] = []
    spoof_seen = False
    changed = False
    min_gap_s = max(0, int(min_gap_minutes)) * 60

    for d in decisions:
        if d.decision == "CONFIRMED" and d.student_id:
            sid = int(d.student_id)
            att = (await db.execute(select(Attendance).where(
                Attendance.schedule_id == schedule_id, Attendance.student_id == sid,
            ))).scalar_one_or_none()
            # Uniform run-once: has_uniform từ pipeline (unknown -> giữ True để không phạt oan)
            has_uniform = True if d.uniform_status in ("ok", "unknown") else False
            note = "face-kiosk-v2"
            if d.uniform_status == "violation":
                note = "face-kiosk-v2+uniform-violation"

            if att is None:
                snap = None
                if frame_bgr is not None:
                    uniform_det = d.uniform_det if d.uniform_det is not None else _detect_uniform(frame_bgr)
                    snap = _img_svc.save_attendance_snapshot(
                        frame_bgr, d.bbox, schedule_id, sid, "in",
                        uniform_det=uniform_det, uniform_status=d.uniform_status)
                db.add(Attendance(
                    schedule_id=schedule_id, student_id=sid,
                    check_in_time=now, has_uniform=has_uniform, status=AttendanceStatus.PRESENT,
                    note=note, updated_by=teacher_id,
                    check_in_snapshot_url=snap,
                ))
                checked_in.append(sid)
                changed = True
                db.add(FaceEvent(schedule_id=schedule_id, student_id=sid,
                                 confidence=d.score, liveness_score=d.liveness, decision="CHECKED_IN"))
            elif att.is_manual_override:
                # Tôn trọng GV sửa tay: kiosk không ghi đè, báo đã xong để UI khỏi spam.
                if sid not in already_done:
                    already_done.append(sid)
            elif att.check_in_time is None:
                att.check_in_time = now
                if att.status == AttendanceStatus.ABSENT:
                    att.status = AttendanceStatus.PRESENT
                # Cập nhật đồng phục nếu phát hiện vi phạm (không ghi đè True -> False oan khi unknown)
                if d.uniform_status == "violation":
                    att.has_uniform = False
                if not att.note:
                    att.note = note
                if frame_bgr is not None and not att.check_in_snapshot_url:
                    try:
                        uniform_det = d.uniform_det if d.uniform_det is not None else _detect_uniform(frame_bgr)
                        att.check_in_snapshot_url = _img_svc.save_attendance_snapshot(
                            frame_bgr, d.bbox, schedule_id, sid, "in",
                            uniform_det=uniform_det, uniform_status=d.uniform_status)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"snapshot check-in lỗi: {e}")
                checked_in.append(sid)
                changed = True
                db.add(FaceEvent(schedule_id=schedule_id, student_id=sid,
                                 confidence=d.score, liveness_score=d.liveness, decision="CHECKED_IN"))
            elif att.check_out_time is None:
                ci = _as_aware(att.check_in_time)
                elapsed = (now - ci).total_seconds() if ci else float("inf")
                if elapsed >= min_gap_s:
                    att.check_out_time = now
                    if frame_bgr is not None:
                        try:
                            uniform_det = d.uniform_det if d.uniform_det is not None else _detect_uniform(frame_bgr)
                            att.check_out_snapshot_url = _img_svc.save_attendance_snapshot(
                                frame_bgr, d.bbox, schedule_id, sid, "out",
                                uniform_det=uniform_det, uniform_status=d.uniform_status)
                        except Exception as e:  # noqa: BLE001
                            logger.warning(f"snapshot check-out lỗi: {e}")
                    checked_out.append(sid)
                    changed = True
                    db.add(FaceEvent(schedule_id=schedule_id, student_id=sid,
                                     confidence=d.score, liveness_score=d.liveness, decision="CHECKED_OUT"))
                # else: quét trùng khi đứng yên trước camera -> bỏ qua lặng lẽ.
            else:
                # Đã đủ check-in + check-out -> bỏ qua, báo hoàn thành.
                if sid not in already_done:
                    already_done.append(sid)
        elif d.decision == "SPOOF":
            spoof_seen = True
            db.add(FaceEvent(schedule_id=schedule_id, student_id=None,
                             confidence=0.0, liveness_score=d.liveness, decision="SPOOF"))
    if changed or spoof_seen:
        await db.commit()
    return {"checked_in": checked_in, "checked_out": checked_out, "already_done": already_done}

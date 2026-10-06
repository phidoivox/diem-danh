from __future__ import annotations

"""Ghi Attendance cho các FaceDecision CONFIRMED (kiosk v2, dùng chung HTTP + WS).

Quy tắc (giữ nguyên từ recognition.service cũ):
- Mỗi người tối đa 2 lượt/tiết: CONFIRMED đầu -> check-in (+ snapshot in),
  CONFIRMED sau (cách check-in >= min_gap) -> check-out (+ snapshot out),
  từ lần 3 -> already_done.
- Quét trùng trong min_gap -> bỏ qua lặng lẽ.
- is_manual_override -> kiosk không ghi đè.
- FaceEvent chỉ log khi transition thật (in/out/spoof).

Đặt ở attendance (owner Attendance) để recognition không import ngược.
"""

from datetime import datetime, timezone
from typing import Any, Iterable

from loguru import logger

from detect_ai.modules.recognition.public import FaceEvent, save_attendance_snapshot
from ..infrastructure.models import Attendance, AttendanceStatus
from ..infrastructure.repos import list_attendances_by_students

#: Khoảng cách tối thiểu giữa check-in và check-out (phút). Có setting
#: CHECKOUT_MIN_GAP_MINUTES trong DB để admin nhìn thấy, nhưng hot-path kiosk
#: (mỗi ~450ms) không query DB nên dùng hằng số này làm mặc định.
MIN_CHECKOUT_GAP_MINUTES = 5

_spoof_last: dict[tuple[int, int], float] = {}


def _as_aware(dt: datetime | None) -> datetime | None:
    """SQLite trả datetime naive, Postgres trả aware -> chuẩn hóa về aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def commit_decisions(
    db: Any,
    schedule_id: int,
    teacher_id: int,
    decisions: Iterable[Any],
    frame_bgr: Any = None,
    min_gap_minutes: int = MIN_CHECKOUT_GAP_MINUTES,
) -> dict:
    """Ghi Attendance + snapshot local + FaceEvent cho các CONFIRMED.

    Trả dict {"checked_in": [...], "checked_out": [...], "already_done": [...]}
    danh sách student_id. Giữ tương thích: caller cũ chỉ đọc checked_in.
    """
    from detect_ai.modules.recognition.public import discard_student

    now = datetime.now(timezone.utc)
    checked_in: list[int] = []
    checked_out: list[int] = []
    already_done: list[int] = []
    spoof_seen = False
    changed = False
    min_gap_s = max(0, int(min_gap_minutes)) * 60

    # Batch SELECT 1 lần: N+1 -> 1 query cho mọi CONFIRMED trong frame.
    decisions = list(decisions)
    sids = sorted({int(d.student_id) for d in decisions
                   if d.decision == "CONFIRMED" and d.student_id})
    by_sid: dict[int, Attendance] = {}
    if sids:
        rows = await list_attendances_by_students(db, schedule_id, sids)
        by_sid = {a.student_id: a for a in rows}

    for d in decisions:
        if d.decision == "CONFIRMED" and d.student_id:
            sid = int(d.student_id)
            att = by_sid.get(sid)
            # Uniform run-once: has_uniform từ pipeline (unknown -> giữ True để không phạt oan)
            has_uniform = True if d.uniform_status in ("ok", "unknown") else False
            note = "face-kiosk-v2"
            if d.uniform_status == "violation":
                note = "face-kiosk-v2+uniform-violation"

            if att is None:
                snap = None
                if frame_bgr is not None:
                    snap = save_attendance_snapshot(
                        frame_bgr, d.bbox, schedule_id, sid, "in",
                        uniform_det=d.uniform_det, uniform_status=d.uniform_status)
                att_new = Attendance(
                    schedule_id=schedule_id, student_id=sid,
                    check_in_time=now, has_uniform=has_uniform, status=AttendanceStatus.PRESENT,
                    note=note, updated_by=teacher_id,
                    check_in_snapshot_url=snap,
                )
                db.add(att_new)
                by_sid[sid] = att_new
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
                        att.check_in_snapshot_url = save_attendance_snapshot(
                            frame_bgr, d.bbox, schedule_id, sid, "in",
                            uniform_det=d.uniform_det, uniform_status=d.uniform_status)
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
                    # Đồng phục lúc ra: violation -> False, ok -> True,
                    # unknown giữ giá trị lúc vào (không phạt oan).
                    if d.uniform_status == "violation":
                        att.has_uniform = False
                    elif d.uniform_status == "ok":
                        att.has_uniform = True
                    try:
                        discard_student(schedule_id, sid)
                    except Exception:  # noqa: BLE001
                        pass
                    if frame_bgr is not None:
                        try:
                            att.check_out_snapshot_url = save_attendance_snapshot(
                                frame_bgr, d.bbox, schedule_id, sid, "out",
                                uniform_det=d.uniform_det, uniform_status=d.uniform_status)
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
            import time as _t
            key = (schedule_id, int(d.student_id) if d.student_id else -d.track_id)
            if _t.monotonic() - _spoof_last.get(key, 0.0) >= 10.0:
                _spoof_last[key] = _t.monotonic()
                spoof_seen = True
                db.add(FaceEvent(schedule_id=schedule_id, student_id=None,
                                 confidence=0.0, liveness_score=d.liveness, decision="SPOOF"))
            # ponytail: cần audit full thì log DB mỗi frame thay vì throttle
    if changed or spoof_seen:
        await db.commit()
    return {"checked_in": checked_in, "checked_out": checked_out, "already_done": already_done}


__all__ = ["MIN_CHECKOUT_GAP_MINUTES", "commit_decisions"]

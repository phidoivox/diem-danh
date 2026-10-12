"""Lịch sử điểm danh 1 SV trong 1 lớp (dùng chung teacher + admin).

Tách từ teacher_routes.get_student_attendance_history: giữ nguyên query,
gộp ledger, summary. Không check quyền — caller tự check trước khi gọi.

Application chỉ gọi repo + đọc thuộc tính ORM, không select trực tiếp
(check_bounds cấm sqlalchemy/fastapi ở layer này).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from detect_ai.shared.kernel.errors import NotFoundError


def _source(att: Any) -> str:
    if att is None:
        return "none"
    if att.is_manual_override:
        return "manual"
    if (att.note or "") and "face-kiosk" in att.note:
        return "face"
    return "teacher"


def _fmt(t: Any) -> str:
    return t.strftime("%H:%M") if hasattr(t, "strftime") else str(t)


def _status_key(status: Any) -> str:
    return status.value if hasattr(status, "value") else str(status)


async def build_student_history(
    db: Any, class_id: int, student_id: int
) -> Dict[str, Any]:
    """Trả dict khớp StudentHistoryResponse (summary/items). 404 nếu sai lớp/SV."""
    from ..infrastructure.repos import get_history_bundle

    class_obj, enrolled, student, schedules, atts, ledger = await get_history_bundle(
        db, class_id, student_id
    )
    if not class_obj:
        raise NotFoundError("Không tìm thấy lớp học phần")
    if not enrolled:
        raise NotFoundError("Sinh viên không thuộc lớp học phần này")

    att_by_sched = {a.schedule_id: a for a in atts}

    summary: Dict[str, int] = {
        "total_sessions": len(schedules),
        "present": 0,
        "late": 0,
        "half_absent": 0,
        "absent": 0,
        "excused": 0,
        "total_deducted": 0,
    }

    # Bulk lấy tổng điểm biến động theo từng buổi (repo đã gộp 1 query).
    delta_by_schedule: Dict[int, int] = {}
    evaluated_schedule_ids: set[int] = set()
    for entry in ledger:
        if entry.schedule_id is None:
            continue
        evaluated_schedule_ids.add(entry.schedule_id)
        delta_by_schedule[entry.schedule_id] = (
            delta_by_schedule.get(entry.schedule_id, 0) + entry.point_delta
        )

    items: List[Dict[str, Any]] = []
    for s in schedules:
        att = att_by_sched.get(s.id)
        point_delta: Optional[int] = (
            delta_by_schedule.get(s.id) if s.id in evaluated_schedule_ids else None
        )
        if point_delta is not None and point_delta < 0:
            summary["total_deducted"] += abs(point_delta)
        base: Dict[str, Any] = {
            "schedule_id": s.id,
            "study_date": s.study_date,
            "start_time": _fmt(s.start_time),
            "end_time": _fmt(s.end_time),
            "session_order": s.session_order,
            "room_name": s.room_name,
            "point_delta": point_delta,
        }
        if att:
            status_val = _status_key(att.status)
            key = status_val.lower()
            if key == "present":
                summary["present"] += 1
            elif key == "late":
                summary["late"] += 1
            elif key == "half_absent":
                summary["half_absent"] += 1
            elif key == "excused":
                summary["excused"] += 1
            else:
                summary["absent"] += 1
            items.append(
                {
                    **base,
                    "attendance_id": att.id,
                    "check_in_time": att.check_in_time,
                    "check_out_time": att.check_out_time,
                    "check_in_snapshot_url": att.check_in_snapshot_url,
                    "check_out_snapshot_url": att.check_out_snapshot_url,
                    "has_uniform": att.has_uniform,
                    "status": status_val,
                    "is_manual_override": att.is_manual_override,
                    "source": _source(att),
                    "note": att.note,
                }
            )
        else:
            summary["absent"] += 1
            items.append({**base, "attendance_id": None})

    return {
        "class_id": class_obj.id,
        "class_code": class_obj.class_code,
        "course_name": class_obj.course_name,
        "student_id": student_id,
        "student_code": student.user_code if student else "",
        "full_name": student.full_name if student else "",
        "summary": summary,
        "items": items,
    }

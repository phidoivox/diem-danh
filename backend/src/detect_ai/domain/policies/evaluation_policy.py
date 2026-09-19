"""Pure attendance decision policy (Task 7).

Tách phép tính thuần khỏi adapter (evaluation_service): không chạm DB,
không import ORM — chỉ nhận giá trị thuần và trả (status, point_delta).

Thứ tự nghiệp vụ (verbatim, giữ nguyên evaluation_service cũ):
  approved -> EXCUSED/0;
  override -> POINT_MAP.get + uniform cộng thêm (trừ EXCUSED);
  check_in None -> ABSENT;
  so tz-naive với start+tol;
  require_checkout và thiếu checkout -> HALF_ABSENT;
  late/present + uniform.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def _name(value: object) -> str:
    """Enum -> .value, còn lại -> str(value)."""
    return value.value if hasattr(value, "value") else str(value)  # type: ignore[union-attr]


def _lookup(points: dict, key: object, default: int = 0) -> int:
    """Tra điểm chịu được cả key enum lẫn key str.

    evaluation_service giữ POINT_MAP key enum AttendanceStatus, trong khi
    policy làm việc với str — hàm này khớp qua .value để hai bên không lệch.
    """
    try:
        if key in points:
            return points[key]  # type: ignore[index]
    except TypeError:
        pass
    s = _name(key)
    if s in points:
        return points[s]
    for k, v in points.items():
        if _name(k) == s:
            return v
    return default


def _uniform_penalty(points: dict) -> int:
    for candidate in ("UNIFORM_VIOLATION", "POINT_UNIFORM_VIOLATION", "UNIFORM"):
        if candidate in points:
            return points[candidate]
        for k, v in points.items():
            if _name(k) == candidate:
                return v
    return 0


def decide_attendance(
    check_in: datetime | None,
    check_out: datetime | None,
    start_dt: datetime,
    late_tol: int,
    require_checkout: bool,
    has_uniform: bool,
    is_override: bool,
    override_status: str | None,
    is_approved: bool,
    points: dict,
) -> tuple[str, int]:
    """Quyết định (status, point_delta) cho một lượt điểm danh.

    - `points`: dict ánh xạ trạng thái -> điểm, chịu cả key enum/str, cộng thêm
      key "UNIFORM_VIOLATION" (số âm) cho phạt đồng phục.
    - `override_status`: trạng thái str do giảng viên override (None -> ABSENT).
    - So sánh tz-naive: strip tzinfo của check_in/start_dt rồi so với
      start + timedelta(minutes=late_tol) — đúng như evaluation_service cũ
      (cin_naive = combine(cin.date(), cin.time())).
    """

    # 1. Đơn nghỉ phép đã duyệt -> EXCUSED, 0 điểm (cao nhất).
    if is_approved:
        return ("EXCUSED", 0)

    # 2. Tôn trọng override thủ công của giảng viên.
    if is_override:
        ov = _name(override_status) if override_status is not None else "ABSENT"
        delta = _lookup(points, override_status if override_status is not None else "ABSENT", 0)
        if not has_uniform and ov != "EXCUSED":
            delta += _uniform_penalty(points)
        return (ov, delta)

    # 3. Không có check-in -> ABSENT (không cộng phạt đồng phục — giữ nguyên
    # evaluation_service cũ: nhánh này không check uniform).
    if check_in is None:
        return ("ABSENT", _lookup(points, "ABSENT", 0))

    # 4. So sánh tz-naive với start + tolerance.
    cin_naive = (
        datetime.combine(check_in.date(), check_in.time())
        if check_in.tzinfo is not None
        else check_in
    )
    start_naive = (
        datetime.combine(start_dt.date(), start_dt.time())
        if getattr(start_dt, "tzinfo", None) is not None
        else start_dt
    )
    late_deadline = start_naive + timedelta(minutes=late_tol)
    is_late = cin_naive > late_deadline

    # 5. Bắt buộc checkout nhưng thiếu -> nửa buổi.
    if require_checkout and check_out is None:
        delta = _lookup(points, "HALF_ABSENT", 0)
        if not has_uniform:
            delta += _uniform_penalty(points)
        return ("HALF_ABSENT", delta)

    # 6. Late/present + phạt đồng phục nếu vi phạm.
    status = "LATE" if is_late else "PRESENT"
    delta = _lookup(points, status, 0)
    if not has_uniform:
        delta += _uniform_penalty(points)
    return (status, delta)

"""Pure conduct-rank classification (6 mức xếp loại điểm rèn luyện).

Nguồn chân lý duy nhất cho khung điểm chuẩn:
  Xuất sắc: chỉ ban cán sự (is_officer) và điểm >= 90.
  SV thường trần ở Tốt kể cả 100 điểm.
  Tốt 80-100, Khá 65-<80, Trung bình 50-<65, Yếu 35-<50, Kém <35.

Cận dưới bao hàm, cận trên loại trừ (trừ 100).
Thuần: không DB, không ORM — theo mẫu policy.py / exam_ban.py.
"""

from __future__ import annotations

RANK_EXCELLENT = "Xuất sắc"
RANK_GOOD = "Tốt"
RANK_FAIR = "Khá"
RANK_AVERAGE = "Trung bình"
RANK_WEAK = "Yếu"
RANK_POOR = "Kém"

# Cận dưới từng mức, giảm dần để loop match đầu tiên.
_RANK_THRESHOLDS: tuple[tuple[str, int], ...] = (
    (RANK_EXCELLENT, 90),
    (RANK_GOOD, 80),
    (RANK_FAIR, 65),
    (RANK_AVERAGE, 50),
    (RANK_WEAK, 35),
)


def classify_conduct(total_point: int | float | None, is_officer: bool = False) -> str:
    """Quy total_point (0..100) ra 1 trong 6 nhãn xếp loại.

    is_officer: ban cán sự 90+ -> Xuất sắc; SV thường trần Tốt kể cả 100.
    """
    if total_point is None:
        total_point = 100
    try:
        point = float(total_point)
    except (TypeError, ValueError):
        point = 100.0
    # ponytail: clamp thay vì throw; upgrade khi muốn 422 cho dữ liệu lệch biên.
    point = min(100.0, max(0.0, point))
    if is_officer and point >= 90:
        return RANK_EXCELLENT
    for label, floor in _RANK_THRESHOLDS[1:]:
        if point >= floor:
            return label
    return RANK_POOR

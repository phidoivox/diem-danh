"""Pure exam-ban conversion policy (Task 7).

V = vắng + 0.5 * nửa_buổi (EXCUSED không tính — việc loại EXCUSED do
report_service đếm ở ngoài, hàm này chỉ quy đổi số).
"""

from __future__ import annotations

HALF_ABSENT_WEIGHT = 0.5


def converted_absent(n_absent: int, n_half: int) -> float:
    """Số buổi vắng quy đổi: n_absent + 0.5 * n_half."""
    return n_absent + HALF_ABSENT_WEIGHT * n_half

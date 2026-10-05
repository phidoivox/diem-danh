from __future__ import annotations

import math
import time
from typing import Mapping, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from detect_ai.models.system_setting import SystemSetting


async def load_settings_map(session: AsyncSession) -> dict[str, str]:
    """Đọc toàn bộ system_settings thành {key: value} trong 1 truy vấn."""
    rows = (await session.execute(select(SystemSetting))).scalars().all()
    return {row.key: row.value for row in rows}


def as_int(settings: Mapping[str, str], key: str, default: int) -> int:
    """Ép giá trị cấu hình sang int, rơi về default nếu thiếu hoặc không hợp lệ."""
    raw = settings.get(key)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def as_bool(settings: Mapping[str, str], key: str, default: bool) -> bool:
    raw = settings.get(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("true", "1", "yes", "t")


def as_float(settings: Mapping[str, str], key: str, default: float) -> float:
    """Ép giá trị cấu hình sang float.

    Dùng cho 2 ngưỡng phần trăm: quy chế có thể là số thập phân (VD 12.5%).
    Trước đây `as_int` khiến "12.5" không parse được ⇒ âm thầm rơi về mặc định,
    admin tưởng đã đổi ngưỡng nhưng báo cáo vẫn dùng 15/20.
    """
    raw = settings.get(key)
    if raw is None:
        return default
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return default
    # "nan"/"inf" parse được nhưng vô nghĩa với ngưỡng % ⇒ coi như giá trị hỏng.
    return value if math.isfinite(value) else default


async def load_exam_ban_thresholds(session: AsyncSession) -> Tuple[float, float]:
    """(ngưỡng cảnh báo lũy kế %, ngưỡng cấm thi cả kỳ %).

    Đây là nguồn duy nhất cho 2 ngưỡng này. Trước đây report_service hardcode
    15.0/20.0 nên đổi cấu hình ở màn Admin không làm báo cáo cấm thi thay đổi.
    """
    settings = await load_settings_map(session)
    warning = as_float(settings, "WARNING_ABSENCE_PERCENT", 15.0)
    ban = as_float(settings, "MAX_ABSENCE_PERCENT_EXAM_BAN", 20.0)
    return warning, ban


# Cache ngắn cho hot-path kiosk (mỗi ~450ms): đọc DB 1 lần/TTL, không query mỗi frame.
_min_gap_cache: dict[str, float | int] = {"value": 5, "at": 0.0}
MIN_GAP_TTL_S = 30.0


async def load_min_checkout_gap(session: AsyncSession) -> int:
    """Khoảng cách tối thiểu check-in -> check-out (phút), cache ngắn 30s.

    Floor 0 để admin có thể tắt chống quét trùng (0 = cho out ngay).
    """
    now = time.monotonic()
    if now - float(_min_gap_cache["at"]) < MIN_GAP_TTL_S:
        return int(_min_gap_cache["value"])
    settings = await load_settings_map(session)
    gap = max(0, as_int(settings, "CHECKOUT_MIN_GAP_MINUTES", 5))
    _min_gap_cache.update(value=gap, at=now)
    return gap

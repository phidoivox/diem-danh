from __future__ import annotations

from typing import Mapping, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.system_setting import SystemSetting


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


async def load_exam_ban_thresholds(session: AsyncSession) -> Tuple[float, float]:
    """(ngưỡng cảnh báo lũy kế %, ngưỡng cấm thi cả kỳ %).

    Đây là nguồn duy nhất cho 2 ngưỡng này. Trước đây report_service hardcode
    15.0/20.0 nên đổi cấu hình ở màn Admin không làm báo cáo cấm thi thay đổi.
    """
    settings = await load_settings_map(session)
    warning = as_int(settings, "WARNING_ABSENCE_PERCENT", 15)
    ban = as_int(settings, "MAX_ABSENCE_PERCENT_EXAM_BAN", 20)
    return float(warning), float(ban)

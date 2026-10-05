"""Tiện ích thời gian dùng chung — mọi mốc "hôm nay" của nghiệp vụ theo giờ Việt Nam.

Lý do tồn tại: server có thể chạy ở múi giờ UTC (Docker/Supabase mặc định).
Trước đây `report_service` và `evaluation_service` dùng `date.today()` (giờ server)
trong khi Kiosk/Giảng viên dùng `Asia/Ho_Chi_Minh`, dẫn tới:
  - báo cáo cấm thi lùi/mất một ngày trong khoảng 00:00–07:00 giờ VN;
  - Cron "23h59" thực chất chạy 06:59 giờ VN và đánh giá sai ngày.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def now_vn() -> datetime:
    """Thời điểm hiện tại theo giờ Việt Nam (timezone-aware)."""
    return datetime.now(VN_TZ)


def today_vn() -> date:
    """Ngày hiện tại theo giờ Việt Nam."""
    return now_vn().date()

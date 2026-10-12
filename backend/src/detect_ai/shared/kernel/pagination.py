from __future__ import annotations

from typing import Sequence
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select


async def paginate_stmt(
    s: AsyncSession,
    stmt: Select,
    page: int,
    size: int,
) -> tuple[Sequence, int]:
    """Phân trang chuẩn cho mọi list endpoint: trả (items, total).

    Thay 3 bản copy `count(subquery) + offset/limit` ở routes_admin_users,
    routes_admin_academic, routes_leave_requests. Giữ nguyên shape response
    `{items, total, page, size}` nên frontend không phải đổi.
    """
    # Trần 500 khớp mọi Query(le=500) khai báo ở routes (users/classes/courses/admin-classes).
    # Helper cũ kẹp 100 nên FE xin size=500 (dropdown lớp SH) lặng lẽ mất dữ liệu.
    page = max(1, int(page or 1))
    size = min(500, max(1, int(size or 20)))
    total = (await s.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    rows = (await s.execute(stmt.offset((page - 1) * size).limit(size))).scalars().all()
    return rows, int(total)

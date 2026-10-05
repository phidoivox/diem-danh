from __future__ import annotations

from typing import Generic, List, TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


T = TypeVar("T")
ModelT = TypeVar("ModelT")


class Page(BaseModel, Generic[T]):
    """Khung phân trang chung {items, total, page, size}.

    Task 3 chỉ định nghĩa — KHÔNG đổi bất kỳ List trần nào sang Page
    (để Task 6 làm cùng frontend).
    """

    items: List[T]
    total: int
    page: int
    size: int


async def get_or_404(
    session: AsyncSession,
    model: type[ModelT],
    id: int,
    detail: str = "Không tìm thấy dữ liệu",
) -> ModelT:
    """Lấy 1 dòng theo khóa chính đơn, raise 404 với message gốc nếu thiếu.

    CHỈ dùng cho model khóa đơn: Class / Schedule / User / LeaveRequest /
    Attendance. CẤM dùng cho ClassStudent (khóa kép class_id + student_id)
    — composite PK không tra được bằng session.get(model, id) đơn.
    """
    obj = await session.get(model, id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return obj

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy.exc import IntegrityError


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Biến lỗi vi phạm ràng buộc DB thành 409 sạch thay vì 500 kèm stack trace.

    Cần thiết vì các bản ghi có thể bị tạo đồng thời: pre-check ở tầng API luôn có
    khe hở TOCTOU, còn ràng buộc DB mới là thứ chặn thật.
    """
    logger.warning(f"Vi phạm ràng buộc dữ liệu tại {request.url.path}: {exc.orig}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Dữ liệu đã tồn tại hoặc vi phạm ràng buộc của hệ thống."},
    )

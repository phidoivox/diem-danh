from __future__ import annotations

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_db
from ..services.evaluation_service import run_nightly_evaluation
from .deps_auth import require_role

router = APIRouter(dependencies=[Depends(require_role("ADMIN"))])


class EvaluationResponse(BaseModel):
    target_date: str
    schedules_evaluated: int
    students_evaluated: int
    total_records: int


@router.post("/run-now", response_model=EvaluationResponse)
async def run_evaluation_now(
    target_date: Optional[date] = Query(
        None, description="Target date for evaluation, defaults to today"
    ),
    s: AsyncSession = Depends(get_db),
):
    """Admin manually triggers nightly attendance evaluation (idempotent)."""
    return await run_nightly_evaluation(s, target_date=target_date)

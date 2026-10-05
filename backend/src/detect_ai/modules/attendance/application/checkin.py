from __future__ import annotations

from typing import Any, Iterable

from detect_ai.modules.recognition.public import commit_decisions
from detect_ai.services.settings_repo import load_min_checkout_gap


async def record_checkin(
    session: Any,
    schedule_id: int,
    teacher_id: int,
    decisions: Iterable[Any],
    frame_bgr: Any = None,
    min_gap_minutes: int | None = None,
) -> dict:
    """Orchestrate recording attendance check-in/out decisions to DB.

    Face identify input (decisions) passed in from presentation/recognition,
    NOT imported engine.
    """
    if min_gap_minutes is None:
        min_gap_minutes = await load_min_checkout_gap(session)

    return await commit_decisions(
        session,
        schedule_id=schedule_id,
        teacher_id=teacher_id,
        decisions=decisions,
        frame_bgr=frame_bgr,
        min_gap_minutes=min_gap_minutes,
    )


__all__ = ["record_checkin"]

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    class_code: str
    course_name: str
    teacher_id: int
    teacher_name: str = ""
    semester: str
    total_sessions: int
    student_count: int = 0


def build_class_response(
    c: Any, teacher_name: str, student_count: int
) -> ClassResponse:
    """Dựng ClassResponse từ ORM Class + 2 field dẫn xuất."""
    resp = ClassResponse.model_validate(c)
    resp.teacher_name = teacher_name
    resp.student_count = student_count
    return resp

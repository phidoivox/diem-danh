from __future__ import annotations
from pydantic import BaseModel

class StudentOut(BaseModel):
    id: int
    code: str
    name: str
    class_name: str
    photo: str = ""

class StudentPage(BaseModel):
    items: list[StudentOut]
    total: int
    page: int
    size: int

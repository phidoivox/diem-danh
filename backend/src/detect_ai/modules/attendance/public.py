from __future__ import annotations

# Debt note (Ruling T7-4): recognition.service imports stay OLD path verbatim.
# Will be rewired to modules.recognition.public in Task 8.
from .application.checkin import record_checkin
from .infrastructure.models import Attendance, AttendanceStatus

__all__ = [
    "record_checkin",
    "Attendance",
    "AttendanceStatus",
]

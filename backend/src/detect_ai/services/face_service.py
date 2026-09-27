from __future__ import annotations

"""Compat wrapper: giữ API cũ cho routes_kiosk/routes_admin_users, ruột là recognition v2.

File gốc (ai/face_runtime + face_gallery + spoof_detector) đã xóa.
"""

from ..recognition import enroll as _enroll

MAX_ACTIVE_PER_USER = _enroll.MAX_ACTIVE_PER_USER
MIN_ENROLL_QUALITY = _enroll.MIN_ENROLL_QUALITY


class EnrollError(_enroll.EnrollError):
    pass


async def enroll_image(db, user_id: int, img_bgr, source: str = "avatar"):
    return await _enroll.enroll_image(db, user_id, img_bgr, source=source)


async def active_count(db, user_id: int) -> int:
    return await _enroll.active_count(db, user_id)

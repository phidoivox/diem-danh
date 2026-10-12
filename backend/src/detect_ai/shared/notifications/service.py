from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from detect_ai.shared.kernel.settings import as_bool, load_settings_map
from detect_ai.shared.kernel.timeutil import today_vn
from . import mailer
from . import templates as T
from .models import NotificationLog


async def _toggles(session) -> Dict[str, bool]:
    m = await load_settings_map(session)
    return {
        "master": as_bool(m, "EMAIL_ENABLED", True),
        "reminder": as_bool(m, "EMAIL_REMINDER_ENABLED", True),
        "warning": as_bool(m, "EMAIL_WARNING_ENABLED", True),
        "ban": as_bool(m, "EMAIL_BAN_ENABLED", True),
    }


async def _existing_keys(session, keys: List[str]) -> set:
    if not keys:
        return set()
    rows = (
        await session.execute(
            select(NotificationLog.dedup_key).where(NotificationLog.dedup_key.in_(keys))
        )
    ).scalars().all()
    return set(rows)


def _log(session, student_id: int, class_id: int, kind: str,
         dedup_key: str, status: str, schedule_id: Optional[int] = None,
         error: Optional[str] = None) -> None:
    session.add(NotificationLog(
        student_id=student_id, class_id=class_id, schedule_id=schedule_id,
        kind=kind, dedup_key=dedup_key, status=status,
        error=(error or "")[:500] if error else None,
    ))


async def _send_one(session, to: str, subject: str, html: str, text: str,
                    student_id: int, class_id: int, kind: str, dedup_key: str,
                    schedule_id: Optional[int] = None, dry_run: bool = False) -> str:
    """Trả về sent | skipped_dedup_n/a | failed | dry_run. Không raise."""
    if dry_run:
        return "dry_run"
    res = await mailer.send(to, subject, html, text, session)
    if res.get("ok"):
        _log(session, student_id, class_id, kind, dedup_key, "sent", schedule_id)
        await asyncio.sleep(0.2)
        return "sent"
    _log(session, student_id, class_id, kind, dedup_key,
         "failed", schedule_id, res.get("error", "unknown"))
    return "failed"


async def send_daily_reminders(session, target_date: Optional[date] = None) -> Dict[str, Any]:
    """Mail nhắc lịch buổi học ngày mai. 1 mail/SV/lớp/ngày."""
    from detect_ai.modules.academic.public import Class, ClassStudent, Schedule
    from detect_ai.modules.identity.public import User

    if target_date is None:
        target_date = today_vn() + timedelta(days=1)
    tg = await _toggles(session)
    if not (tg["master"] and tg["reminder"]):
        return {"sent": 0, "skipped": 0, "failed": 0, "disabled": True}

    scheds = (
        await session.execute(
            select(Schedule)
            .options(
                selectinload(Schedule.clazz).selectinload(Class.teacher),
            )
            .where(Schedule.study_date == target_date)
            .order_by(Schedule.start_time)
        )
    ).scalars().all()
    if not scheds:
        return {"sent": 0, "skipped": 0, "failed": 0, "schedules": 0}

    # Gom buổi theo (class_id, student) — batch 2 query: enroll + users.
    class_ids = list({s.class_id for s in scheds})
    enroll = (
        await session.execute(
            select(ClassStudent).where(ClassStudent.class_id.in_(class_ids))
        )
    ).scalars().all()
    by_class: Dict[int, List[int]] = {}
    for e in enroll:
        by_class.setdefault(e.class_id, []).append(e.student_id)
    all_sids = list({sid for v in by_class.values() for sid in v})
    users = []
    if all_sids:
        users = (
            await session.execute(
                select(User).where(
                    User.id.in_(all_sids),
                    User.is_active == True,  # noqa: E712
                    User.deleted_at.is_(None),
                )
            )
        ).scalars().all()
    email_by_id = {u.id: (u.email, u.full_name) for u in users}

    # Nhóm buổi theo SV trong từng lớp.
    groups: Dict[tuple, List] = {}
    for s in scheds:
        for sid in by_class.get(s.class_id, []):
            if sid in email_by_id:
                groups.setdefault((s.class_id, sid), []).append(s)

    keys = [f"reminder:{c}:{sid}:{target_date.isoformat()}" for c, sid in groups]
    seen = await _existing_keys(session, keys)
    sent = skipped = failed = 0
    for (class_id, sid), ss in groups:
        key = f"reminder:{class_id}:{sid}:{target_date.isoformat()}"
        if key in seen:
            skipped += 1
            continue
        email, name = email_by_id[sid]
        sched_dicts = [{
            "course_name": s.clazz.course_name if s.clazz else "",
            "class_code": s.clazz.class_code if s.clazz else "",
            "session_order": s.session_order,
            "study_date": str(s.study_date),
            "start_time": str(s.start_time), "end_time": str(s.end_time),
            "room_name": s.room_name,
            "teacher_name": s.clazz.teacher.full_name if s.clazz and s.clazz.teacher else "",
        } for s in ss]
        subject, html, text = T.reminder_mail(name, sched_dicts)
        r = await _send_one(session, email, subject, html, text, sid, class_id, "reminder", key)
        if r == "sent":
            sent += 1
        else:
            failed += 1
    await session.commit()
    logger.info(f"[reminder] date={target_date} sent={sent} skipped={skipped} failed={failed}")
    return {"sent": sent, "skipped": skipped, "failed": failed, "date": str(target_date)}


async def send_schedule_reminder(session, schedule_id: int, dry_run: bool = False) -> Dict[str, Any]:
    """Gửi bù nhắc 1 buổi cụ thể. Dedup theo schedule_id."""
    from detect_ai.modules.academic.public import Class, Schedule
    from detect_ai.modules.reporting.public import list_enrolled_students

    tg = await _toggles(session)
    if not (tg["master"] and tg["reminder"]):
        return {"sent": 0, "skipped": 0, "failed": 0, "disabled": True}
    sched = (
        await session.execute(
            select(Schedule)
            .options(selectinload(Schedule.clazz).selectinload(Class.teacher))
            .where(Schedule.id == schedule_id)
        )
    ).scalars().first()
    if not sched:
        return {"sent": 0, "skipped": 0, "failed": 0, "error": "schedule_not_found"}
    students = await list_enrolled_students(session, sched.class_id)
    keys = [f"reminder-one:{sched.class_id}:{st.id}:{schedule_id}" for st in students]
    seen = await _existing_keys(session, keys)
    sent = skipped = failed = 0
    for st in students:
        key = f"reminder-one:{sched.class_id}:{st.id}:{schedule_id}"
        if key in seen:
            skipped += 1
            continue
        sched_dict = [{
            "course_name": sched.clazz.course_name if sched.clazz else "",
            "class_code": sched.clazz.class_code if sched.clazz else "",
            "session_order": sched.session_order,
            "study_date": str(sched.study_date),
            "start_time": str(sched.start_time), "end_time": str(sched.end_time),
            "room_name": sched.room_name,
            "teacher_name": sched.clazz.teacher.full_name if sched.clazz and sched.clazz.teacher else "",
        }]
        subject, html, text = T.reminder_mail(st.full_name, sched_dict)
        r = await _send_one(session, st.email, subject, html, text, st.id,
                            sched.class_id, "reminder", key, schedule_id, dry_run)
        if r == "sent":
            sent += 1
        elif r == "dry_run":
            skipped += 1
        else:
            failed += 1
    if not dry_run:
        await session.commit()
    return {"sent": sent, "skipped": skipped, "failed": failed}


async def _class_warnings(session, class_id: int, only: str,
                          day: str, dry_run: bool) -> Dict[str, int]:
    from detect_ai.modules.reporting.public import calculate_class_exam_ban
    from detect_ai.modules.identity.public import User

    tg = await _toggles(session)
    rep = await calculate_class_exam_ban(session, class_id)
    if not rep:
        return {"sent": 0, "skipped": 0, "failed": 0, "error": "class_not_found"}  # type: ignore
    students = rep.get("students", [])
    ids = [s["student_id"] for s in students]
    users = []
    if ids:
        users = (
            await session.execute(
                select(User).where(
                    User.id.in_(ids),
                    User.is_active == True,  # noqa: E712
                    User.deleted_at.is_(None),
                )
            )
        ).scalars().all()
    email_by_id = {u.id: u.email for u in users}
    warn_pct = rep.get("warning_percent", 15.0)
    ban_pct = rep.get("ban_percent", 20.0)
    sent = skipped = failed = 0
    targets = []
    for st in students:
        if st.get("is_banned"):
            kind = "banned"
        elif st.get("is_warning"):
            kind = "warning"
        else:
            continue
        if only != "all" and only != kind and not (only == "banned" and kind == "banned"):
            continue
        if kind == "warning" and not tg["warning"]:
            continue
        if kind == "banned" and not tg["ban"]:
            continue
        targets.append((st, kind))
    keys = [f"exam:{k}:{class_id}:{st['student_id']}:{day}" for st, k in targets]
    seen = await _existing_keys(session, keys)
    for st, kind in targets:
        key = f"exam:{kind}:{class_id}:{st['student_id']}:{day}"
        if key in seen:
            skipped += 1
            continue
        email = email_by_id.get(st["student_id"], "")
        if kind == "banned":
            subject, html, text = T.banned_mail(st, ban_pct)
        else:
            subject, html, text = T.warning_mail(st, warn_pct, ban_pct)
        r = await _send_one(session, email, subject, html, text,
                            st["student_id"], class_id, kind, key,
                            dry_run=dry_run)
        if r == "sent":
            sent += 1
        elif r == "dry_run":
            skipped += 1
        else:
            failed += 1
    return {"sent": sent, "skipped": skipped, "failed": failed}


async def send_exam_digest(session, reference_date: Optional[date] = None) -> Dict[str, Any]:
    """Digest sau nightly: duyệt mọi lớp, gửi warning/banned. 1 mail/SV/lớp/ngày."""
    from detect_ai.modules.reporting.public import list_classes_ordered

    tg = await _toggles(session)
    if not tg["master"]:
        return {"sent": 0, "skipped": 0, "failed": 0, "disabled": True}
    day = str(reference_date or today_vn())
    classes = await list_classes_ordered(session)
    total = {"sent": 0, "skipped": 0, "failed": 0}
    for c in classes:
        r = await _class_warnings(session, c.id, "all", day, False)
        for k in total:
            total[k] += int(r.get(k, 0) or 0)
    await session.commit()
    logger.info(f"[exam-digest] day={day} {total}")
    return {**total, "day": day}


async def send_class_exam_warnings(session, class_id: int, only: str = "all",
                                   dry_run: bool = False) -> Dict[str, Any]:
    day = str(today_vn())
    r = await _class_warnings(session, class_id, only, day, dry_run)
    if not dry_run:
        await session.commit()
    return r

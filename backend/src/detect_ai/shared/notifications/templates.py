from __future__ import annotations

from typing import Dict, List


def reminder_subject(n: int) -> str:
    return f"[Lịch học ngày mai] Bạn có {n} buổi học"


def _sched_line(s: Dict) -> str:
    return (
        f"<li><b>{s.get('course_name','')}</b> ({s.get('class_code','')}) — "
        f"Buổi {s.get('session_order','')} · {s.get('study_date','')} "
        f"{str(s.get('start_time',''))[:5]}–{str(s.get('end_time',''))[:5]} · "
        f"Phòng {s.get('room_name','')} · GV {s.get('teacher_name','')}</li>"
    )


def reminder_mail(name: str, schedules: List[Dict]) -> tuple[str, str, str]:
    items = "".join(_sched_line(s) for s in schedules)
    subject = reminder_subject(len(schedules))
    html = (
        f"<p>Chào {name},</p><p>Ngày mai bạn có <b>{len(schedules)}</b> buổi học:</p>"
        f"<ul>{items}</ul><p>Nhớ mang đồng phục và đến đúng giờ.</p>"
    )
    text = f"Chào {name}, ngày mai bạn có {len(schedules)} buổi học. Xem chi tiết trên portal."
    return subject, html, text


def warning_mail(st: Dict, warning_pct: float, ban_pct: float) -> tuple[str, str, str]:
    subject = f"[CẢNH BÁO cấm thi] {st.get('course_name','')} ({st.get('class_code','')})"
    html = (
        f"<p>Chào {st.get('full_name','')},</p>"
        f"<p>Môn <b>{st.get('course_name','')}</b> lớp {st.get('class_code','')}:</p>"
        f"<ul><li>Vắng: {st.get('absent_count',0)} buổi, nửa buổi: {st.get('half_absent_count',0)}</li>"
        f"<li>Vắng quy đổi: {st.get('converted_absent',0)}</li>"
        f"<li>Tỷ lệ lũy kế: {st.get('rate_cumulative',0)}% (ngưỡng cảnh báo {warning_pct}%)</li>"
        f"<li>Tỷ lệ cả kỳ: {st.get('rate_semester',0)}% (ngưỡng cấm thi {ban_pct}%)</li></ul>"
        f"<p>Đi học đầy đủ các buổi còn lại để tránh bị cấm thi.</p>"
    )
    text = (
        f"Cảnh báo cấm thi môn {st.get('course_name','')}: "
        f"lũy kế {st.get('rate_cumulative',0)}% >= {warning_pct}%."
    )
    return subject, html, text


def banned_mail(st: Dict, ban_pct: float) -> tuple[str, str, str]:
    subject = f"[CẤM THI] {st.get('course_name','')} ({st.get('class_code','')})"
    html = (
        f"<p>Chào {st.get('full_name','')},</p>"
        f"<p>Bạn đã <b>BỊ CẤM THI</b> môn <b>{st.get('course_name','')}</b> "
        f"lớp {st.get('class_code','')}.</p>"
        f"<ul><li>Vắng quy đổi: {st.get('converted_absent',0)}</li>"
        f"<li>Tỷ lệ cả kỳ: {st.get('rate_semester',0)}% (ngưỡng {ban_pct}%)</li></ul>"
        f"<p>Liên hệ giảng viên / phòng đào tạo để xác nhận.</p>"
    )
    text = (
        f"Cấm thi môn {st.get('course_name','')}: "
        f"cả kỳ {st.get('rate_semester',0)}% >= {ban_pct}%."
    )
    return subject, html, text

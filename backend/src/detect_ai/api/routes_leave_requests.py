from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.deps import get_db
from ..models.academic import Class, ClassStudent, Schedule
from ..models.attendance_v2 import Attendance, AttendanceStatus
from ..models.leave_request import LeaveRequest, LeaveStatus
from ..models.point_ledger import PointLedger
from ..models.user import StudentProfile, User
from ..services.storage_service import upload_leave_proof
from .deps_auth import require_teacher, require_student
from .helpers import get_or_404

router = APIRouter()


# =====================================================================
# SCHEMAS
# =====================================================================
class LeaveRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int
    student_id: int
    reason: str
    proof_image: Optional[str] = None
    status: str
    teacher_feedback: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    course_name: Optional[str] = None
    class_code: Optional[str] = None
    study_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    room_name: Optional[str] = None
    student_code: Optional[str] = None
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    avatar_url: Optional[str] = None
    class_name: Optional[str] = None


class LeaveRequestPage(BaseModel):
    items: List[LeaveRequestResponse]
    total: int
    page: int
    size: int


class ReviewLeaveRequestSchema(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    feedback: Optional[str] = None


def format_leave_request(leave: LeaveRequest) -> dict:
    sched = leave.schedule
    clazz = sched.clazz if sched else None
    stu = leave.student
    sp = stu.student_profile if stu else None

    return {
        "id": leave.id,
        "schedule_id": leave.schedule_id,
        "student_id": leave.student_id,
        "reason": leave.reason,
        "proof_image": leave.proof_image,
        "status": leave.status.value if isinstance(leave.status, LeaveStatus) else leave.status,
        "teacher_feedback": leave.teacher_feedback,
        "reviewed_by": leave.reviewed_by,
        "reviewed_at": leave.reviewed_at,
        "created_at": leave.created_at,
        "course_name": clazz.course_name if clazz else None,
        "class_code": clazz.class_code if clazz else None,
        "study_date": sched.study_date if sched else None,
        "start_time": sched.start_time if sched else None,
        "end_time": sched.end_time if sched else None,
        "room_name": sched.room_name if sched else None,
        "student_code": stu.user_code if stu else None,
        "student_name": stu.full_name if stu else None,
        "student_email": stu.email if stu else None,
        "avatar_url": stu.avatar_url if stu else None,
        "class_name": sp.class_name if sp else None,
    }


# =====================================================================
# SINH VIÊN (STUDENT) ENDPOINTS
# =====================================================================
@router.post(
    "/api/v1/student/leave-requests",
    response_model=LeaveRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Sinh viên nộp đơn xin nghỉ phép",
)
async def submit_leave_request(
    schedule_id: int = Form(...),
    reason: str = Form(...),
    proof_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    # 1. Kiểm tra schedule tồn tại
    sched_stmt = (
        select(Schedule)
        .options(selectinload(Schedule.clazz))
        .where(Schedule.id == schedule_id)
    )
    sched_res = await db.execute(sched_stmt)
    schedule = sched_res.scalar_one_or_none()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy lịch học của buổi học này",
        )

    # 2. Kiểm tra sinh viên có trong lớp học phần
    cs_stmt = select(ClassStudent).where(
        ClassStudent.class_id == schedule.class_id,
        ClassStudent.student_id == current_user.id,
    )
    cs_res = await db.execute(cs_stmt)
    if not cs_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sinh viên không thuộc lớp học phần của buổi học này",
        )

    # 3. Tránh nộp trùng: nếu đã có đơn PENDING hoặc APPROVED cho buổi học này
    dup_stmt = select(LeaveRequest).where(
        LeaveRequest.schedule_id == schedule_id,
        LeaveRequest.student_id == current_user.id,
        LeaveRequest.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
    )
    dup_res = await db.execute(dup_stmt)
    if dup_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đã có đơn nghỉ phép cho buổi học này",
        )

    # 4. Upload minh chứng nếu có
    proof_url = None
    if proof_file is not None and proof_file.filename:
        proof_url = await upload_leave_proof(proof_file)

    # 5. Tạo bản ghi đơn nghỉ phép
    leave_request = LeaveRequest(
        schedule_id=schedule_id,
        student_id=current_user.id,
        reason=reason.strip(),
        proof_image=proof_url,
        status=LeaveStatus.PENDING,
    )
    db.add(leave_request)
    await db.commit()
    await db.refresh(leave_request)

    # Load relationship for response
    full_stmt = (
        select(LeaveRequest)
        .options(
            selectinload(LeaveRequest.schedule).selectinload(Schedule.clazz),
            selectinload(LeaveRequest.student).selectinload(User.student_profile),
        )
        .where(LeaveRequest.id == leave_request.id)
    )
    loaded_leave = (await db.execute(full_stmt)).scalar_one()
    return format_leave_request(loaded_leave)


@router.get(
    "/api/v1/student/leave-requests",
    response_model=List[LeaveRequestResponse],
    summary="Sinh viên xem danh sách các đơn nghỉ phép của mình",
)
async def get_student_leave_requests(
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(LeaveRequest)
        .options(
            selectinload(LeaveRequest.schedule).selectinload(Schedule.clazz),
            selectinload(LeaveRequest.student).selectinload(User.student_profile),
        )
        .where(LeaveRequest.student_id == current_user.id)
        .order_by(LeaveRequest.created_at.desc())
    )
    res = await db.execute(stmt)
    leaves = res.scalars().all()
    return [format_leave_request(l) for l in leaves]


# =====================================================================
# GIẢNG VIÊN (TEACHER) ENDPOINTS
# =====================================================================
@router.get(
    "/api/v1/teacher/leave-requests",
    response_model=LeaveRequestPage,
    summary="Giảng viên xem danh sách đơn nghỉ phép của các lớp mình phụ trách",
)
async def get_teacher_leave_requests(
    status_filter: Optional[str] = Query(None, alias="status", description="PENDING, APPROVED, REJECTED"),
    class_id: Optional[int] = Query(None, description="Lọc theo lớp học phần"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    # Lấy các đơn nghỉ phép thuộc lớp do current_user phụ trách
    stmt = (
        select(LeaveRequest)
        .join(Schedule, LeaveRequest.schedule_id == Schedule.id)
        .join(Class, Schedule.class_id == Class.id)
        .where(Class.teacher_id == current_user.id)
    )

    if class_id:
        stmt = stmt.where(Class.id == class_id)

    if status_filter:
        norm_status = status_filter.strip().upper()
        if norm_status in LeaveStatus.__members__:
            stmt = stmt.where(LeaveRequest.status == LeaveStatus[norm_status])

    # Count total + paginate (helper dùng chung toàn codebase)
    from ..core.pagination import paginate_stmt

    stmt = (
        stmt.options(
            selectinload(LeaveRequest.schedule).selectinload(Schedule.clazz),
            selectinload(LeaveRequest.student).selectinload(User.student_profile),
        )
        .order_by(LeaveRequest.created_at.desc())
    )
    leaves, total = await paginate_stmt(db, stmt, page, size)

    return LeaveRequestPage(
        items=[LeaveRequestResponse(**format_leave_request(l)) for l in leaves],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/api/v1/teacher/leave-requests/{id}/review",
    response_model=LeaveRequestResponse,
    summary="Giảng viên duyệt hoặc từ chối đơn nghỉ phép",
)
async def review_leave_request(
    id: int,
    payload: ReviewLeaveRequestSchema,
    current_user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    # 1. 404 cho khóa đơn qua get_or_404 (giữ nguyên message), rồi nạp eager
    # schedule.clazz + student.student_profile bằng đúng query cũ để giữ
    # nguyên nghiệp vụ duyệt (async cấm lazy-load sau commit).
    await get_or_404(db, LeaveRequest, id, detail="Đơn nghỉ phép không tồn tại")
    stmt = (
        select(LeaveRequest)
        .options(
            selectinload(LeaveRequest.schedule).selectinload(Schedule.clazz),
            selectinload(LeaveRequest.student).selectinload(User.student_profile),
        )
        .where(LeaveRequest.id == id)
    )
    leave_req = (await db.execute(stmt)).scalar_one()

    # 2. Kiểm tra quyền sở hữu lớp học phần
    class_obj = leave_req.schedule.clazz if leave_req.schedule else None
    if not class_obj or class_obj.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền duyệt đơn của lớp học phần này",
        )

    # 3. Cập nhật trạng thái đơn
    review_status = LeaveStatus[payload.status]
    leave_req.status = review_status
    leave_req.teacher_feedback = payload.feedback.strip() if payload.feedback else None
    leave_req.reviewed_by = current_user.id
    leave_req.reviewed_at = datetime.now(timezone.utc)

    # 4. Nghiệp vụ phê duyệt (APPROVED)
    if review_status == LeaveStatus.APPROVED:
        # 4.1 Tìm hoặc tạo bản ghi attendance
        att_stmt = select(Attendance).where(
            Attendance.schedule_id == leave_req.schedule_id,
            Attendance.student_id == leave_req.student_id,
        )
        att_res = await db.execute(att_stmt)
        attendance = att_res.scalar_one_or_none()

        if not attendance:
            attendance = Attendance(
                schedule_id=leave_req.schedule_id,
                student_id=leave_req.student_id,
                status=AttendanceStatus.EXCUSED,
            )
            db.add(attendance)
        else:
            attendance.status = AttendanceStatus.EXCUSED

        # 4.2 Cơ chế Hoàn điểm duyệt muộn (Late Approval Refund Logic)
        if attendance and attendance.is_evaluated:
            # Kiểm tra xem sinh viên đã bị trừ bao nhiêu điểm do buổi học này
            ledger_stmt = select(PointLedger).where(
                PointLedger.student_id == leave_req.student_id,
                PointLedger.schedule_id == leave_req.schedule_id,
                PointLedger.point_delta < 0,
            )
            deduct_records = (await db.execute(ledger_stmt)).scalars().all()

            # Tránh hoàn điểm 2 lần
            refund_check_stmt = select(PointLedger).where(
                PointLedger.student_id == leave_req.student_id,
                PointLedger.schedule_id == leave_req.schedule_id,
                PointLedger.reason_code == "LEAVE_REFUND",
            )
            already_refunded = (await db.execute(refund_check_stmt)).scalar_one_or_none()

            if deduct_records and not already_refunded:
                refund_points = sum(abs(r.point_delta) for r in deduct_records)
                class_code_str = class_obj.class_code if class_obj else ""

                refund_entry = PointLedger(
                    student_id=leave_req.student_id,
                    schedule_id=leave_req.schedule_id,
                    point_delta=refund_points,
                    reason_code="LEAVE_REFUND",
                    description=f"Hoàn điểm chuyên cần do đơn nghỉ phép được duyệt bổ sung (Lớp {class_code_str})",
                )
                db.add(refund_entry)

                # Cập nhật tăng điểm cho sinh viên trong student_profiles
                sp_stmt = select(StudentProfile).where(
                    StudentProfile.user_id == leave_req.student_id
                )
                profile = (await db.execute(sp_stmt)).scalar_one_or_none()
                if profile:
                    profile.total_point += refund_points

    await db.commit()
    await db.refresh(leave_req)

    return format_leave_request(leave_req)

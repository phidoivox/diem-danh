from __future__ import annotations

from datetime import date, datetime, time
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from detect_ai.shared.kernel.storage_service import upload_leave_proof_bytes
from detect_ai.modules.academic.public import Class, ClassStudent, Schedule
from detect_ai.modules.identity.public import User
from detect_ai.modules.identity.public import require_student, require_teacher
from detect_ai.shared.kernel.deps import get_db
from ..application.review import review_leave as review_leave_use_case
from ..infrastructure.models import LeaveRequest, LeaveStatus

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

    # 4. Upload minh chứng nếu có (biên: UploadFile -> bytes rồi gọi port,
    # validate jpeg/png/pdf 5MB + UUID giữ nguyên trong adapter)
    proof_url = None
    if proof_file is not None and proof_file.filename:
        proof_content = await proof_file.read()
        proof_url = await upload_leave_proof_bytes(
            proof_content, proof_file.content_type, proof_file.filename
        )

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
    from detect_ai.shared.kernel.pagination import paginate_stmt

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
    # 1. Nạp đơn + eager schedule.clazz + student.student_profile trong 1 query
    # (gộp double-fetch: bỏ get_or_404 + scalar_one() riêng lẻ; async cấm
    # lazy-load sau commit nên giữ nguyên eager options).
    stmt = (
        select(LeaveRequest)
        .options(
            selectinload(LeaveRequest.schedule).selectinload(Schedule.clazz),
            selectinload(LeaveRequest.student).selectinload(User.student_profile),
        )
        .where(LeaveRequest.id == id)
    )
    leave_req = (await db.execute(stmt)).scalar_one_or_none()
    if leave_req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Đơn nghỉ phép không tồn tại",
        )

    # 2. Kiểm tra quyền sở hữu lớp học phần
    class_obj = leave_req.schedule.clazz if leave_req.schedule else None
    if not class_obj or class_obj.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền duyệt đơn của lớp học phần này",
        )

    # 3. Route thin: validate xong -> gọi use-case (giữ đúng thứ tự nghiệp vụ
    # status -> EXCUSED -> refund check -> commit/rollback/refresh trong use-case).
    review_status = LeaveStatus[payload.status]
    leave_req = await review_leave_use_case(
        db,
        leave=leave_req,
        new_status=review_status,
        feedback=payload.feedback,
        reviewer_id=current_user.id,
    )

    return format_leave_request(leave_req)


__all__ = [
    "LeaveRequestPage",
    "LeaveRequestResponse",
    "ReviewLeaveRequestSchema",
    "format_leave_request",
    "get_student_leave_requests",
    "get_teacher_leave_requests",
    "review_leave_request",
    "router",
    "submit_leave_request",
]

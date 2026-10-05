from __future__ import annotations

from datetime import date, time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.pagination import paginate_stmt
from ..infrastructure.models import Class, ClassStudent, Schedule
from detect_ai.models.user import Role, StudentProfile, User
from detect_ai.modules.identity.public import require_admin
from detect_ai.api.dto import ClassResponse, build_class_response
from detect_ai.api.helpers import get_or_404

router = APIRouter(dependencies=[Depends(require_admin)])


async def check_room_conflict(
    s: AsyncSession,
    room_name: str,
    study_date: date,
    start_time: time,
    end_time: time,
    exclude_schedule_id: Optional[int] = None,
) -> Optional[Schedule]:
    """Một helper duy nhất cho chống trùng phòng (create + update dùng chung).

    Overlap <=> existing.start < new_end AND existing.end > new_start.
    Update truyền exclude_schedule_id để không tự trùng với chính mình.
    """
    stmt = select(Schedule).where(
        Schedule.room_name == room_name,
        Schedule.study_date == study_date,
        Schedule.start_time < end_time,
        Schedule.end_time > start_time,
    )
    if exclude_schedule_id is not None:
        stmt = stmt.where(Schedule.id != exclude_schedule_id)
    return (await s.execute(stmt)).scalars().first()


# =====================================================================
# SCHEMAS
# =====================================================================
class ClassPage(BaseModel):
    items: List[ClassResponse]
    total: int
    page: int
    size: int


class ClassCreateRequest(BaseModel):
    class_code: str = Field(..., min_length=1)
    course_name: str = Field(..., min_length=1)
    teacher_id: int
    semester: str = Field(..., min_length=1)
    total_sessions: int = Field(15, ge=1)


class ClassUpdateRequest(BaseModel):
    class_code: Optional[str] = None
    course_name: Optional[str] = None
    teacher_id: Optional[int] = None
    semester: Optional[str] = None
    total_sessions: Optional[int] = None


class StudentInClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_code: str
    full_name: str
    email: str
    class_name: Optional[str] = None
    major: Optional[str] = None
    total_point: Optional[int] = None


class EnrollStudentRequest(BaseModel):
    student_id: int


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    class_id: int
    class_code: Optional[str] = None
    course_name: Optional[str] = None
    room_name: str
    study_date: date
    start_time: time
    end_time: time
    session_order: int


class ScheduleCreateRequest(BaseModel):
    class_id: int
    room_name: str = Field(..., min_length=1)
    study_date: date
    start_time: time
    end_time: time
    session_order: int = Field(1, ge=1)


class ScheduleUpdateRequest(BaseModel):
    class_id: Optional[int] = None
    room_name: Optional[str] = None
    study_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    session_order: Optional[int] = None


# =====================================================================
# CLASSES CRUD
# =====================================================================
@router.get("/classes", response_model=ClassPage)
async def list_classes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=500),
    q: str = Query("", description="Search by class_code or course_name"),
    s: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Class)
        .options(
            selectinload(Class.teacher),
        )
    )

    if q.strip():
        search = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Class.class_code.ilike(search),
                Class.course_name.ilike(search),
            )
        )

    classes, total = await paginate_stmt(
        s, stmt.order_by(Class.id.desc()), page, size,
    )

    # Đếm sĩ số 1 query cho cả trang (GROUP BY) thay N+1 query từng lớp.
    class_ids = [c.id for c in classes]
    counts: dict[int, int] = {}
    if class_ids:
        rows = (
            await s.execute(
                select(ClassStudent.class_id, func.count(ClassStudent.student_id))
                .where(ClassStudent.class_id.in_(class_ids))
                .group_by(ClassStudent.class_id)
            )
        ).all()
        counts = {cid: cnt for cid, cnt in rows}

    # Calculate student count for each class
    items = []
    for c in classes:
        student_cnt = counts.get(c.id, 0)

        teacher_name = c.teacher.full_name if c.teacher else ""
        items.append(build_class_response(c, teacher_name, student_cnt))

    return ClassPage(items=items, total=total, page=page, size=size)


@router.post("/classes", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    body: ClassCreateRequest,
    s: AsyncSession = Depends(get_db),
):
    # Check duplicate class_code
    existing = (
        await s.execute(select(Class).where(Class.class_code == body.class_code.strip()))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã lớp '{body.class_code}' đã tồn tại trong hệ thống",
        )

    # Check teacher exists
    teacher = (
        await s.execute(
            select(User).where(User.id == body.teacher_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy giảng viên có ID {body.teacher_id}",
        )

    new_class = Class(
        class_code=body.class_code.strip(),
        course_name=body.course_name.strip(),
        teacher_id=body.teacher_id,
        semester=body.semester.strip(),
        total_sessions=body.total_sessions,
    )
    s.add(new_class)
    await s.commit()
    await s.refresh(new_class)

    return ClassResponse(
        id=new_class.id,
        class_code=new_class.class_code,
        course_name=new_class.course_name,
        teacher_id=new_class.teacher_id,
        teacher_name=teacher.full_name,
        semester=new_class.semester,
        total_sessions=new_class.total_sessions,
        student_count=0,
    )


@router.put("/classes/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: int,
    body: ClassUpdateRequest,
    s: AsyncSession = Depends(get_db),
):
    stmt = select(Class).options(selectinload(Class.teacher)).where(Class.id == class_id)
    clazz = (await s.execute(stmt)).scalar_one_or_none()
    if not clazz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lớp học phần có ID {class_id}",
        )

    if body.class_code is not None and body.class_code.strip() != clazz.class_code:
        dup = (
            await s.execute(
                select(Class).where(Class.class_code == body.class_code.strip())
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mã lớp '{body.class_code}' đã tồn tại",
            )
        clazz.class_code = body.class_code.strip()

    if body.course_name is not None:
        clazz.course_name = body.course_name.strip()

    if body.teacher_id is not None and body.teacher_id != clazz.teacher_id:
        teacher = (
            await s.execute(
                select(User).where(User.id == body.teacher_id, User.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy giảng viên có ID {body.teacher_id}",
            )
        clazz.teacher_id = body.teacher_id

    if body.semester is not None:
        clazz.semester = body.semester.strip()

    if body.total_sessions is not None:
        if body.total_sessions < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="total_sessions phải >= 1",
            )
        clazz.total_sessions = body.total_sessions

    await s.commit()

    # Reload
    stmt = select(Class).options(selectinload(Class.teacher)).where(Class.id == class_id)
    clazz = (await s.execute(stmt)).scalar_one()

    cnt_res = await s.execute(
        select(func.count(ClassStudent.student_id)).where(ClassStudent.class_id == clazz.id)
    )
    student_cnt = cnt_res.scalar() or 0

    return ClassResponse(
        id=clazz.id,
        class_code=clazz.class_code,
        course_name=clazz.course_name,
        teacher_id=clazz.teacher_id,
        teacher_name=clazz.teacher.full_name if clazz.teacher else "",
        semester=clazz.semester,
        total_sessions=clazz.total_sessions,
        student_count=student_cnt,
    )


@router.delete("/classes/{class_id}")
async def delete_class(
    class_id: int,
    s: AsyncSession = Depends(get_db),
):
    clazz = await get_or_404(s, Class, class_id, detail=f"Không tìm thấy lớp học phần có ID {class_id}")

    await s.delete(clazz)
    await s.commit()
    return {"ok": True, "message": "Class deleted successfully"}


# =====================================================================
# CLASS STUDENTS ENROLLMENT
# =====================================================================
@router.get("/classes/{class_id}/students", response_model=List[StudentInClassResponse])
async def list_class_students(
    class_id: int,
    s: AsyncSession = Depends(get_db),
):
    clazz = await get_or_404(s, Class, class_id, detail=f"Không tìm thấy lớp học phần có ID {class_id}")

    stmt = (
        select(User)
        .join(ClassStudent, ClassStudent.student_id == User.id)
        .options(selectinload(User.student_profile))
        .where(
            ClassStudent.class_id == class_id,
            User.deleted_at.is_(None),
        )
        .order_by(User.user_code)
    )
    students = (await s.execute(stmt)).scalars().all()

    return [
        StudentInClassResponse(
            id=stu.id,
            user_code=stu.user_code,
            full_name=stu.full_name,
            email=stu.email,
            class_name=stu.student_profile.class_name if stu.student_profile else "",
            major=stu.student_profile.major if stu.student_profile else "",
            total_point=stu.student_profile.total_point if stu.student_profile else 100,
        )
        for stu in students
    ]


@router.post("/classes/{class_id}/students", status_code=status.HTTP_201_CREATED)
async def enroll_student(
    class_id: int,
    body: EnrollStudentRequest,
    s: AsyncSession = Depends(get_db),
):
    clazz = await get_or_404(s, Class, class_id, detail=f"Không tìm thấy lớp học phần có ID {class_id}")

    # Check student exists and is active
    student = (
        await s.execute(
            select(User)
            .options(selectinload(User.role))
            .where(User.id == body.student_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sinh viên có ID {body.student_id}",
        )

    # Check if duplicate in class_students
    existing = (
        await s.execute(
            select(ClassStudent).where(
                ClassStudent.class_id == class_id,
                ClassStudent.student_id == body.student_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sinh viên {student.user_code} đã có trong lớp này!",
        )

    enrollment = ClassStudent(class_id=class_id, student_id=body.student_id)
    s.add(enrollment)
    await s.commit()

    return {"ok": True, "class_id": class_id, "student_id": body.student_id}


@router.delete("/classes/{class_id}/students/{student_id}")
async def remove_student_from_class(
    class_id: int,
    student_id: int,
    s: AsyncSession = Depends(get_db),
):
    enrollment = (
        await s.execute(
            select(ClassStudent).where(
                ClassStudent.class_id == class_id,
                ClassStudent.student_id == student_id,
            )
        )
    ).scalar_one_or_none()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sinh viên không thuộc lớp này",
        )

    await s.delete(enrollment)
    await s.commit()
    return {"ok": True, "message": "Student removed from class"}


# =====================================================================
# SCHEDULES CRUD WITH ANTI-COLLISION ROOM CONSTRAINT
# =====================================================================
@router.get("/schedules", response_model=List[ScheduleResponse])
async def list_schedules(
    class_id: Optional[int] = Query(None),
    study_date: Optional[date] = Query(None),
    room_name: Optional[str] = Query(None),
    s: AsyncSession = Depends(get_db),
):
    stmt = select(Schedule).options(selectinload(Schedule.clazz))

    if class_id is not None:
        stmt = stmt.where(Schedule.class_id == class_id)
    if study_date is not None:
        stmt = stmt.where(Schedule.study_date == study_date)
    if room_name is not None and room_name.strip():
        stmt = stmt.where(Schedule.room_name == room_name.strip())

    stmt = stmt.order_by(Schedule.study_date, Schedule.start_time)
    schedules = (await s.execute(stmt)).scalars().all()

    return [
        ScheduleResponse(
            id=sch.id,
            class_id=sch.class_id,
            class_code=sch.clazz.class_code if sch.clazz else None,
            course_name=sch.clazz.course_name if sch.clazz else None,
            room_name=sch.room_name,
            study_date=sch.study_date,
            start_time=sch.start_time,
            end_time=sch.end_time,
            session_order=sch.session_order,
        )
        for sch in schedules
    ]


@router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleCreateRequest,
    s: AsyncSession = Depends(get_db),
):
    # 1. Check time order
    if body.start_time >= body.end_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_time phải nhỏ hơn end_time",
        )

    # 2. Check class exists
    clazz = await get_or_404(s, Class, body.class_id, detail=f"Không tìm thấy lớp học phần có ID {body.class_id}")

    # 3. Check anti-collision room constraint (helper dùng chung với update):
    room_clean = body.room_name.strip()
    conflicting = await check_room_conflict(
        s, room_clean, body.study_date, body.start_time, body.end_time
    )
    if conflicting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phòng học {room_clean} đã có lịch học trong khung giờ này!",
        )

    new_schedule = Schedule(
        class_id=body.class_id,
        room_name=room_clean,
        study_date=body.study_date,
        start_time=body.start_time,
        end_time=body.end_time,
        session_order=body.session_order,
    )
    s.add(new_schedule)
    await s.commit()
    await s.refresh(new_schedule)

    return ScheduleResponse(
        id=new_schedule.id,
        class_id=new_schedule.class_id,
        class_code=clazz.class_code,
        course_name=clazz.course_name,
        room_name=new_schedule.room_name,
        study_date=new_schedule.study_date,
        start_time=new_schedule.start_time,
        end_time=new_schedule.end_time,
        session_order=new_schedule.session_order,
    )


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    body: ScheduleUpdateRequest,
    s: AsyncSession = Depends(get_db),
):
    sched = (
        await s.execute(
            select(Schedule).options(selectinload(Schedule.clazz)).where(Schedule.id == schedule_id)
        )
    ).scalar_one_or_none()
    if not sched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lịch học có ID {schedule_id}",
        )

    if body.class_id is not None and body.class_id != sched.class_id:
        clazz = await get_or_404(s, Class, body.class_id, detail=f"Không tìm thấy lớp học phần có ID {body.class_id}")
        sched.class_id = body.class_id

    if body.room_name is not None and body.room_name.strip():
        sched.room_name = body.room_name.strip()
    if body.study_date is not None:
        sched.study_date = body.study_date
    if body.start_time is not None:
        sched.start_time = body.start_time
    if body.end_time is not None:
        sched.end_time = body.end_time
    if body.session_order is not None:
        if body.session_order < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="session_order phải >= 1",
            )
        sched.session_order = body.session_order

    # 1. Check time order (trên giá trị sau khi gộp)
    if sched.start_time >= sched.end_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_time phải nhỏ hơn end_time",
        )

    # 2. Check anti-collision room constraint, LOẠI TRỪ chính buổi đang sửa
    # (nếu không, mọi lần sửa — kể cả không đổi giờ — đều tự báo trùng với chính nó)
    conflicting = await check_room_conflict(
        s, sched.room_name, sched.study_date, sched.start_time, sched.end_time,
        exclude_schedule_id=schedule_id,
    )
    if conflicting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phòng học {sched.room_name} đã có lịch học trong khung giờ này!",
        )

    await s.commit()
    await s.refresh(sched)

    clazz = sched.clazz or (
        await s.execute(select(Class).where(Class.id == sched.class_id))
    ).scalar_one_or_none()
    return ScheduleResponse(
        id=sched.id,
        class_id=sched.class_id,
        class_code=clazz.class_code if clazz else None,
        course_name=clazz.course_name if clazz else None,
        room_name=sched.room_name,
        study_date=sched.study_date,
        start_time=sched.start_time,
        end_time=sched.end_time,
        session_order=sched.session_order,
    )


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    s: AsyncSession = Depends(get_db),
):
    sched = (
        await s.execute(select(Schedule).where(Schedule.id == schedule_id))
    ).scalar_one_or_none()
    if not sched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy lịch học có ID {schedule_id}",
        )

    await s.delete(sched)
    await s.commit()
    return {"ok": True, "message": "Schedule deleted successfully"}

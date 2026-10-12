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
from ..infrastructure.models import AdministrativeClass, Class, ClassStudent, Course, Schedule


def _resolve_course_code(name: str) -> str:
    """Sinh mã môn từ tên nhập tay (form tạo lớp cho phép nhập tên mới)."""
    import re

    code = re.sub(r"[^A-Z0-9]+", "_", (name or "").strip().upper()).strip("_")
    return (code or "MON_MOI")[:50]


async def _resolve_course_for_class(
    s: AsyncSession, course_id: int | None, course_name: str | None
) -> Course:
    """Resolve course cho lớp học phần: ưu tiên course_id, fallback tên (tự tạo nếu chưa có)."""
    from fastapi import HTTPException as _HTTPException  # local để giữ import head gọn

    if course_id is not None:
        course = await s.get(Course, course_id)
        if course is None:
            raise _HTTPException(
                status_code=404, detail=f"Không tìm thấy học phần có ID {course_id}"
            )
        return course
    name = (course_name or "").strip()
    if not name:
        raise _HTTPException(status_code=422, detail="Vui lòng chọn học phần cho lớp học")
    hit = (
        await s.execute(
            select(Course).where((Course.course_name == name) | (Course.course_code == name.upper()))
        )
    ).scalar_one_or_none()
    if hit is not None:
        return hit
    code = _resolve_course_code(name)
    dup = 0
    base = code
    while (
        await s.execute(select(Course).where(Course.course_code == code))
    ).scalar_one_or_none() is not None:
        dup += 1
        code = f"{base}_{dup}"[:50]
    course = Course(course_code=code, course_name=name)
    s.add(course)
    await s.flush()
    return course


from detect_ai.modules.identity.public import Role, StudentProfile, User
from detect_ai.modules.identity.public import require_admin
from detect_ai.modules.academic.presentation.dto import ClassResponse, build_class_response
from detect_ai.shared.kernel.helpers import get_or_404

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
    course_id: Optional[int] = None
    course_name: Optional[str] = None
    teacher_id: int
    semester: str = Field(..., min_length=1)
    total_sessions: int = Field(15, ge=1)


class ClassUpdateRequest(BaseModel):
    class_code: Optional[str] = None
    course_id: Optional[int] = None
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
    is_officer: bool = False


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


class ScheduleBulkRequest(BaseModel):
    class_id: int
    room_name: str = Field(..., min_length=1)
    start_date: date
    start_time: time
    end_time: time
    # 0=Thứ 2 ... 6=Chủ nhật (khớp date.weekday())
    weekdays: List[int] = Field(..., min_length=1)
    total_sessions: int = Field(15, ge=1, le=60)
    start_session_order: Optional[int] = Field(None, ge=1)


class ScheduleBulkSkipped(BaseModel):
    study_date: date
    reason: str


class ScheduleBulkResponse(BaseModel):
    created: List[ScheduleResponse]
    skipped: List[ScheduleBulkSkipped]


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
            selectinload(Class.course),
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

    course = await _resolve_course_for_class(s, body.course_id, body.course_name)

    new_class = Class(
        class_code=body.class_code.strip(),
        course_id=course.id,
        course_name=course.course_name,
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
        course_id=course.id,
        course_code=course.course_code,
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

    if body.course_id is not None or body.course_name is not None:
        course = await _resolve_course_for_class(s, body.course_id, body.course_name)
        clazz.course_id = course.id
        clazz.course_name = course.course_name

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

    # Reload (nạp cả course: response trả course_code, thiếu là lazy-load nổ 500 trên async)
    stmt = (
        select(Class)
        .options(selectinload(Class.teacher), selectinload(Class.course))
        .where(Class.id == class_id)
    )
    clazz = (await s.execute(stmt)).scalar_one()

    cnt_res = await s.execute(
        select(func.count(ClassStudent.student_id)).where(ClassStudent.class_id == clazz.id)
    )
    student_cnt = cnt_res.scalar() or 0

    course = getattr(clazz, "course", None)
    return ClassResponse(
        id=clazz.id,
        class_code=clazz.class_code,
        course_id=clazz.course_id,
        course_code=course.course_code if course else None,
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

    # Chan xoa khi da co ledger cham diem (xoa cascade se lam PointLedger mo coi schedule_id).
    sched_ids = (await s.execute(select(Schedule.id).where(Schedule.class_id == class_id))).scalars().all()
    if sched_ids:
        from detect_ai.modules.evaluation.public import PointLedger
        n_ledger = (await s.execute(select(func.count()).select_from(PointLedger).where(PointLedger.schedule_id.in_(sched_ids)))).scalar() or 0
        if n_ledger:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lớp đã có {n_ledger} bản ghi chấm điểm, không thể xóa (giữ toàn vẹn sổ điểm)",
            )

    await s.delete(clazz)
    await s.commit()
    return {"ok": True, "message": "Class deleted successfully"}


# =====================================================================
# COURSES CATALOG (danh mục học phần)
# =====================================================================
class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_code: str
    course_name: str
    credits: int
    default_sessions: int
    description: Optional[str] = None
    created_at: Optional[object] = None


class CoursePage(BaseModel):
    items: List[CourseResponse]
    total: int
    page: int
    size: int


class CourseCreateRequest(BaseModel):
    course_code: str = Field(..., min_length=1)
    course_name: str = Field(..., min_length=1)
    credits: int = Field(3, ge=1)
    default_sessions: int = Field(15, ge=1)
    description: Optional[str] = None


class CourseUpdateRequest(BaseModel):
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    credits: Optional[int] = None
    default_sessions: Optional[int] = None
    description: Optional[str] = None


@router.get("/courses", response_model=CoursePage)
async def list_courses(
    page: int = Query(1, ge=1),
    size: int = Query(15, ge=1, le=500),
    q: str = Query("", description="Search by course_code or course_name"),
    s: AsyncSession = Depends(get_db),
):
    stmt = select(Course)
    if q.strip():
        search = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Course.course_code.ilike(search), Course.course_name.ilike(search))
        )
    rows, total = await paginate_stmt(s, stmt.order_by(Course.id.desc()), page, size)
    return CoursePage(
        items=[CourseResponse.model_validate(c) for c in rows],
        total=total, page=page, size=size,
    )


@router.post("/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(body: CourseCreateRequest, s: AsyncSession = Depends(get_db)):
    code = body.course_code.strip().upper()
    dup = (
        await s.execute(select(Course).where(Course.course_code == code))
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã học phần '{code}' đã tồn tại",
        )
    course = Course(
        course_code=code,
        course_name=body.course_name.strip(),
        credits=body.credits,
        default_sessions=body.default_sessions,
        description=(body.description or "").strip() or None,
    )
    s.add(course)
    await s.commit()
    await s.refresh(course)
    return CourseResponse.model_validate(course)


@router.put("/courses/{course_id}", response_model=CourseResponse)
async def update_course(course_id: int, body: CourseUpdateRequest, s: AsyncSession = Depends(get_db)):
    course = await get_or_404(s, Course, course_id, detail=f"Không tìm thấy học phần có ID {course_id}")
    if body.course_code is not None and body.course_code.strip().upper() != course.course_code:
        code = body.course_code.strip().upper()
        dup = (
            await s.execute(select(Course).where(Course.course_code == code))
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mã học phần '{code}' đã tồn tại",
            )
        course.course_code = code
    if body.course_name is not None:
        course.course_name = body.course_name.strip()
    if body.credits is not None:
        if body.credits < 1:
            raise HTTPException(status_code=422, detail="credits phải >= 1")
        course.credits = body.credits
    if body.default_sessions is not None:
        if body.default_sessions < 1:
            raise HTTPException(status_code=422, detail="default_sessions phải >= 1")
        course.default_sessions = body.default_sessions
    if body.description is not None:
        course.description = body.description.strip() or None
    await s.commit()
    await s.refresh(course)
    return CourseResponse.model_validate(course)


@router.delete("/courses/{course_id}")
async def delete_course(course_id: int, s: AsyncSession = Depends(get_db)):
    course = await get_or_404(s, Course, course_id, detail=f"Không tìm thấy học phần có ID {course_id}")
    used = (
        await s.execute(select(func.count(Class.id)).where(Class.course_id == course_id))
    ).scalar() or 0
    if used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Học phần {course.course_code} đang dùng cho {used} lớp, không thể xóa",
        )
    await s.delete(course)
    await s.commit()
    return {"ok": True, "message": "Course deleted successfully"}


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
            is_officer=bool(stu.student_profile.is_officer) if stu.student_profile else False,
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
    role_name = student.role.role_name if student.role else ""
    if role_name != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ tài khoản STUDENT mới được ghi danh (ID {body.student_id} là {role_name or 'không rõ vai trò'})",
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


class BulkEnrollRequest(BaseModel):
    student_ids: List[int] = Field(default_factory=list)
    class_names: List[str] = Field(default_factory=list)
    admin_class_ids: List[int] = Field(default_factory=list)


@router.post("/classes/{class_id}/students/bulk")
async def bulk_enroll_students(
    class_id: int,
    body: BulkEnrollRequest,
    s: AsyncSession = Depends(get_db),
):
    """Ghi danh hàng loạt: theo student_ids + SV thuộc lớp SH (class_names/admin_class_ids)."""
    await get_or_404(s, Class, class_id, detail=f"Không tìm thấy lớp học phần có ID {class_id}")
    target_ids: set[int] = {int(i) for i in (body.student_ids or []) if i}
    sh_codes = [c.strip() for c in (body.class_names or []) if str(c).strip()]
    sh_ids = [int(i) for i in (body.admin_class_ids or []) if i]
    if sh_codes or sh_ids:
        stmt = (
            select(StudentProfile.user_id)
            .join(AdministrativeClass, AdministrativeClass.id == StudentProfile.admin_class_id)
            .where(StudentProfile.admin_class_id.is_not(None))
        )
        conds = []
        if sh_ids:
            conds.append(StudentProfile.admin_class_id.in_(sh_ids))
        if sh_codes:
            conds.append(AdministrativeClass.class_code.in_(sh_codes))
        if conds:
            from sqlalchemy import or_ as _or

            stmt = stmt.where(_or(*conds))
            rows = (await s.execute(stmt)).scalars().all()
            target_ids.update(int(i) for i in rows)
        if sh_codes and not sh_ids:
            legacy = (
                await s.execute(
                    select(User.id).join(StudentProfile, StudentProfile.user_id == User.id).where(
                        StudentProfile.class_name.in_(sh_codes),
                        User.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
            target_ids.update(int(i) for i in legacy)
    enrolled: list[int] = []
    skipped: list[int] = []
    for sid in sorted(target_ids):
        stu = (
            await s.execute(select(User).where(User.id == sid, User.deleted_at.is_(None)))
        ).scalar_one_or_none()
        if stu is None:
            skipped.append(sid)
            continue
        dup = (
            await s.execute(
                select(ClassStudent).where(
                    ClassStudent.class_id == class_id, ClassStudent.student_id == sid
                )
            )
        ).scalar_one_or_none()
        if dup:
            skipped.append(sid)
            continue
        s.add(ClassStudent(class_id=class_id, student_id=sid))
        enrolled.append(sid)
    await s.commit()
    return {"ok": True, "enrolled": enrolled, "skipped": skipped}


# =====================================================================
# ADMINISTRATIVE CLASSES (lớp sinh hoạt)
# =====================================================================
class AdministrativeClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    class_code: str
    academic_year: str = ""
    faculty: str = ""
    homeroom_teacher_id: Optional[int] = None
    homeroom_teacher_name: str = ""
    student_count: int = 0
    created_at: Optional[object] = None


class AdministrativeClassPage(BaseModel):
    items: List[AdministrativeClassResponse]
    total: int
    page: int
    size: int


class AdministrativeClassCreateRequest(BaseModel):
    class_code: str = Field(..., min_length=1)
    academic_year: Optional[str] = ""
    faculty: Optional[str] = ""
    homeroom_teacher_id: Optional[int] = None


class AdministrativeClassUpdateRequest(BaseModel):
    class_code: Optional[str] = None
    academic_year: Optional[str] = None
    faculty: Optional[str] = None
    homeroom_teacher_id: Optional[int] = None


async def _admin_class_item(s: AsyncSession, ac: AdministrativeClass) -> AdministrativeClassResponse:
    cnt = (
        await s.execute(
            select(func.count(StudentProfile.id)).where(StudentProfile.admin_class_id == ac.id)
        )
    ).scalar() or 0
    teacher_name = ""
    if ac.homeroom_teacher_id:
        t = await s.get(User, ac.homeroom_teacher_id)
        teacher_name = t.full_name if t else ""
    return AdministrativeClassResponse(
        id=ac.id,
        class_code=ac.class_code,
        academic_year=ac.academic_year or "",
        faculty=ac.faculty or "",
        homeroom_teacher_id=ac.homeroom_teacher_id,
        homeroom_teacher_name=teacher_name,
        student_count=int(cnt),
        created_at=getattr(ac, "created_at", None),
    )


@router.get("/administrative-classes", response_model=AdministrativeClassPage)
async def list_administrative_classes(
    page: int = Query(1, ge=1),
    size: int = Query(15, ge=1, le=500),
    q: str = Query("", description="Search by class_code or faculty"),
    s: AsyncSession = Depends(get_db),
):
    stmt = select(AdministrativeClass)
    if q.strip():
        search = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                AdministrativeClass.class_code.ilike(search),
                AdministrativeClass.faculty.ilike(search),
            )
        )
    rows, total = await paginate_stmt(s, stmt.order_by(AdministrativeClass.id.desc()), page, size)
    return AdministrativeClassPage(
        items=[await _admin_class_item(s, ac) for ac in rows],
        total=total, page=page, size=size,
    )


@router.post("/administrative-classes", response_model=AdministrativeClassResponse, status_code=status.HTTP_201_CREATED)
async def create_administrative_class(body: AdministrativeClassCreateRequest, s: AsyncSession = Depends(get_db)):
    code = body.class_code.strip().upper()
    dup = (
        await s.execute(select(AdministrativeClass).where(AdministrativeClass.class_code == code))
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=400, detail=f"Mã lớp sinh hoạt '{code}' đã tồn tại")
    if body.homeroom_teacher_id is not None:
        t = (
            await s.execute(select(User).where(User.id == body.homeroom_teacher_id, User.deleted_at.is_(None)))
        ).scalar_one_or_none()
        if t is None:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy giảng viên có ID {body.homeroom_teacher_id}")
    ac = AdministrativeClass(
        class_code=code,
        academic_year=(body.academic_year or "").strip(),
        faculty=(body.faculty or "").strip(),
        homeroom_teacher_id=body.homeroom_teacher_id,
    )
    s.add(ac)
    await s.commit()
    await s.refresh(ac)
    return await _admin_class_item(s, ac)


@router.put("/administrative-classes/{admin_class_id}", response_model=AdministrativeClassResponse)
async def update_administrative_class(admin_class_id: int, body: AdministrativeClassUpdateRequest, s: AsyncSession = Depends(get_db)):
    ac = await get_or_404(s, AdministrativeClass, admin_class_id, detail=f"Không tìm thấy lớp sinh hoạt có ID {admin_class_id}")
    if body.class_code is not None and body.class_code.strip().upper() != ac.class_code:
        code = body.class_code.strip().upper()
        dup = (
            await s.execute(select(AdministrativeClass).where(AdministrativeClass.class_code == code))
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(status_code=400, detail=f"Mã lớp sinh hoạt '{code}' đã tồn tại")
        ac.class_code = code
    if body.academic_year is not None:
        ac.academic_year = body.academic_year.strip()
    if body.faculty is not None:
        ac.faculty = body.faculty.strip()
    if body.homeroom_teacher_id is not None:
        if body.homeroom_teacher_id:
            t = (
                await s.execute(select(User).where(User.id == body.homeroom_teacher_id, User.deleted_at.is_(None)))
            ).scalar_one_or_none()
            if t is None:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy giảng viên có ID {body.homeroom_teacher_id}")
        ac.homeroom_teacher_id = body.homeroom_teacher_id or None
    await s.commit()
    await s.refresh(ac)
    return await _admin_class_item(s, ac)


@router.delete("/administrative-classes/{admin_class_id}")
async def delete_administrative_class(admin_class_id: int, s: AsyncSession = Depends(get_db)):
    ac = await get_or_404(s, AdministrativeClass, admin_class_id, detail=f"Không tìm thấy lớp sinh hoạt có ID {admin_class_id}")
    await s.delete(ac)
    await s.commit()
    return {"ok": True, "message": "Administrative class deleted successfully"}


@router.get("/administrative-classes/{admin_class_id}/students", response_model=List[StudentInClassResponse])
async def list_administrative_class_students(admin_class_id: int, s: AsyncSession = Depends(get_db)):
    await get_or_404(s, AdministrativeClass, admin_class_id, detail=f"Không tìm thấy lớp sinh hoạt có ID {admin_class_id}")
    stmt = (
        select(User)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .where(StudentProfile.admin_class_id == admin_class_id, User.deleted_at.is_(None))
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
            is_officer=bool(stu.student_profile.is_officer) if stu.student_profile else False,
        )
        for stu in students
    ]


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


@router.post("/schedules/bulk", response_model=ScheduleBulkResponse, status_code=status.HTTP_201_CREATED)
async def create_schedules_bulk(
    body: ScheduleBulkRequest,
    s: AsyncSession = Depends(get_db),
):
    # Validate khung giờ + thứ trong tuần trước khi sinh.
    if body.start_time >= body.end_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_time phải nhỏ hơn end_time",
        )
    weekdays = sorted(set(body.weekdays))
    if any(w < 0 or w > 6 for w in weekdays):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="weekdays chỉ nhận 0 (Thứ 2) đến 6 (Chủ nhật)",
        )
    clazz = await get_or_404(s, Class, body.class_id, detail=f"Không tìm thấy lớp học phần có ID {body.class_id}")
    room_clean = body.room_name.strip()
    # STT bắt đầu: mặc định nối sau buổi lớn nhất đã có của lớp.
    if body.start_session_order is not None:
        next_order = body.start_session_order
    else:
        cur_max = (await s.execute(select(func.max(Schedule.session_order)).where(Schedule.class_id == body.class_id))).scalar_one_or_none() or 0
        next_order = int(cur_max) + 1
    created: list[Schedule] = []
    skipped: list[dict] = []
    # Sinh ngày học: duyệt từ start_date, chỉ lấy ngày khớp weekdays, đủ total_sessions thì dừng.
    from datetime import timedelta as _td
    cur = body.start_date
    guard = 0
    while len(created) < body.total_sessions and guard < body.total_sessions * 14 + 14:
        guard += 1
        if cur.weekday() not in weekdays:
            cur += _td(days=1)
            continue
        # Bỏ qua ngày đã có lịch của chính lớp này (tránh đè khi sinh nối tiếp).
        dup = (await s.execute(select(Schedule).where(Schedule.class_id == body.class_id, Schedule.study_date == cur))).scalars().first()
        if dup is not None:
            skipped.append({"study_date": cur, "reason": f"Lớp đã có buổi {dup.session_order} ngày {cur.isoformat()}"})
            cur += _td(days=1)
            continue
        conflict = await check_room_conflict(s, room_clean, cur, body.start_time, body.end_time)
        if conflict is not None:
            skipped.append({"study_date": cur, "reason": f"Phòng {room_clean} trùng lịch ngày {cur.isoformat()}"})
            cur += _td(days=1)
            continue
        sch = Schedule(
            class_id=body.class_id,
            room_name=room_clean,
            study_date=cur,
            start_time=body.start_time,
            end_time=body.end_time,
            session_order=next_order,
        )
        s.add(sch)
        created.append(sch)
        next_order += 1
        cur += _td(days=1)
    await s.commit()
    for sch in created:
        await s.refresh(sch)
    return ScheduleBulkResponse(
        created=[
            ScheduleResponse(
                id=sch.id, class_id=sch.class_id, class_code=clazz.class_code, course_name=clazz.course_name,
                room_name=sch.room_name, study_date=sch.study_date, start_time=sch.start_time,
                end_time=sch.end_time, session_order=sch.session_order,
            )
            for sch in created
        ],
        skipped=[ScheduleBulkSkipped(study_date=item["study_date"], reason=item["reason"]) for item in skipped],
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


class SendReminderRequest(BaseModel):
    dry_run: bool = False


@router.post("/schedules/{schedule_id}/send-reminder")
async def send_schedule_reminder_manual(
    schedule_id: int,
    body: SendReminderRequest,
    s: AsyncSession = Depends(get_db),
):
    """Admin gửi bù mail nhắc 1 buổi học."""
    from detect_ai.shared.notifications import service as notif_service

    return await notif_service.send_schedule_reminder(s, schedule_id, body.dry_run)

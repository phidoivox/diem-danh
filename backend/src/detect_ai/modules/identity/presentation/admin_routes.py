from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from detect_ai.modules.recognition.public import decode_upload, upload_avatar_image
from detect_ai.shared.kernel.deps import get_db
from detect_ai.shared.kernel.pagination import paginate_stmt
from detect_ai.shared.kernel.security import get_password_hash
from ..infrastructure.models import Role, StudentProfile, TeacherProfile, User
from .deps import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


# =====================================================================
# SCHEMAS
# =====================================================================
class StudentProfileDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    total_point: int
    is_officer: bool = False
    admin_class_id: Optional[int] = None
    class_name: str
    major: str


class TeacherProfileDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    department: str
    academic_title: str
    office_room: str


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_code: str
    full_name: str
    email: str
    role: str
    is_active: bool
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    student_profile: Optional[StudentProfileDTO] = None
    teacher_profile: Optional[TeacherProfileDTO] = None


class AdminUserPage(BaseModel):
    items: List[AdminUserResponse]
    total: int
    page: int
    size: int


class UserCreateRequest(BaseModel):
    user_code: str = Field(..., min_length=1)
    full_name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)
    role_name: str = Field(..., description="'ADMIN' | 'TEACHER' | 'STUDENT'")

    # StudentProfile fields
    admin_class_id: Optional[int] = None
    class_name: Optional[str] = ""
    major: Optional[str] = ""
    is_officer: Optional[bool] = None

    # TeacherProfile fields
    department: Optional[str] = ""
    academic_title: Optional[str] = ""
    office_room: Optional[str] = ""


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

    # StudentProfile fields
    admin_class_id: Optional[int] = None
    class_name: Optional[str] = None
    major: Optional[str] = None
    is_officer: Optional[bool] = None

    # TeacherProfile fields
    department: Optional[str] = None
    academic_title: Optional[str] = None
    office_room: Optional[str] = None


def serialize_admin_user(user: User) -> AdminUserResponse:
    role_str = user.role.role_name if user.role else ""
    student_dto = None
    if user.student_profile:
        student_dto = StudentProfileDTO(
            id=user.student_profile.id,
            user_id=user.student_profile.user_id,
            total_point=user.student_profile.total_point,
            is_officer=bool(getattr(user.student_profile, "is_officer", False)),
            admin_class_id=user.student_profile.admin_class_id,
            class_name=user.student_profile.class_name,
            major=user.student_profile.major,
        )
    teacher_dto = None
    if user.teacher_profile:
        teacher_dto = TeacherProfileDTO(
            id=user.teacher_profile.id,
            user_id=user.teacher_profile.user_id,
            department=user.teacher_profile.department,
            academic_title=user.teacher_profile.academic_title,
            office_room=user.teacher_profile.office_room,
        )
    return AdminUserResponse(
        id=user.id,
        user_code=user.user_code,
        full_name=user.full_name,
        email=user.email,
        role=role_str,
        is_active=user.is_active,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        student_profile=student_dto,
        teacher_profile=teacher_dto,
    )


# =====================================================================
# ENDPOINTS
# =====================================================================
@router.get("", response_model=AdminUserPage)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=500),
    role: str = Query("", description="Filter by role: ADMIN, TEACHER, STUDENT"),
    q: str = Query("", description="Search by user_code, full_name, email"),
    s: AsyncSession = Depends(get_db),
):
    stmt = (
        select(User)
        .options(
            selectinload(User.role),
            selectinload(User.student_profile),
            selectinload(User.teacher_profile),
        )
        .where(User.deleted_at.is_(None))
    )

    if role.strip():
        role_upper = role.strip().upper()
        stmt = stmt.join(User.role).where(Role.role_name == role_upper)

    if q.strip():
        search = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                User.user_code.ilike(search),
                User.full_name.ilike(search),
                User.email.ilike(search),
            )
        )

    users, total = await paginate_stmt(
        s, stmt.order_by(User.id.desc()), page, size,
    )

    items = [serialize_admin_user(u) for u in users]
    return AdminUserPage(items=items, total=total, page=page, size=size)


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    s: AsyncSession = Depends(get_db),
):
    # Check user_code duplicate
    existing_code = (
        await s.execute(select(User).where(User.user_code == body.user_code.strip()))
    ).scalar_one_or_none()
    if existing_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã người dùng '{body.user_code}' đã tồn tại trong hệ thống",
        )

    # Check email duplicate
    existing_email = (
        await s.execute(select(User).where(User.email == body.email.strip().lower()))
    ).scalar_one_or_none()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{body.email}' đã tồn tại trong hệ thống",
        )

    # Find role
    role_upper = body.role_name.strip().upper()
    role_obj = (
        await s.execute(select(Role).where(Role.role_name == role_upper))
    ).scalar_one_or_none()
    if not role_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vai trò '{body.role_name}' không hợp lệ. Chọn ADMIN, TEACHER hoặc STUDENT",
        )

    # Create User
    new_user = User(
        user_code=body.user_code.strip(),
        full_name=body.full_name.strip(),
        email=body.email.strip().lower(),
        password_hash=get_password_hash(body.password),
        role_id=role_obj.id,
        is_active=True,
    )
    s.add(new_user)
    await s.flush()

    # Create profile
    if role_upper == "STUDENT":
        admin_class = None
        admin_class_id = body.admin_class_id
        if admin_class_id is not None:
            from detect_ai.modules.academic.public import AdministrativeClass

            admin_class = await s.get(AdministrativeClass, admin_class_id)
            if admin_class is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Không tìm thấy lớp sinh hoạt có ID {admin_class_id}",
                )
        is_officer = bool(body.is_officer) if body.is_officer is not None else False
        student_prof = StudentProfile(
            user_id=new_user.id,
            admin_class_id=admin_class_id,
            class_name=(body.class_name or (admin_class.class_code if admin_class else "")) or "",
            major=body.major or "",
            total_point=100 if is_officer else 95,
            is_officer=is_officer,
        )
        s.add(student_prof)
    elif role_upper == "TEACHER":
        teacher_prof = TeacherProfile(
            user_id=new_user.id,
            department=body.department or "",
            academic_title=body.academic_title or "",
            office_room=body.office_room or "",
        )
        s.add(teacher_prof)

    await s.commit()

    # Reload user with relationships
    stmt = (
        select(User)
        .options(
            selectinload(User.role),
            selectinload(User.student_profile),
            selectinload(User.teacher_profile),
        )
        .where(User.id == new_user.id)
    )
    user_loaded = (await s.execute(stmt)).scalar_one()
    return serialize_admin_user(user_loaded)


@router.put("/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    s: AsyncSession = Depends(get_db),
):
    stmt = (
        select(User)
        .options(
            selectinload(User.role),
            selectinload(User.student_profile),
            selectinload(User.teacher_profile),
        )
        .where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = (await s.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng có ID {user_id}",
        )

    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.email is not None:
        email_clean = body.email.strip().lower()
        if email_clean != user.email:
            dup = (
                await s.execute(select(User).where(User.email == email_clean))
            ).scalar_one_or_none()
            if dup:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email '{email_clean}' đã được sử dụng bởi tài khoản khác",
                )
            user.email = email_clean
    if body.password is not None and body.password.strip():
        user.password_hash = get_password_hash(body.password.strip())
    if body.is_active is not None:
        user.is_active = body.is_active

    # Update StudentProfile if student
    if user.student_profile:
        if body.admin_class_id is not None:
            if body.admin_class_id:
                from detect_ai.modules.academic.public import AdministrativeClass

                admin_class = await s.get(AdministrativeClass, body.admin_class_id)
                if admin_class is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Không tìm thấy lớp sinh hoạt có ID {body.admin_class_id}",
                    )
                user.student_profile.admin_class_id = body.admin_class_id
                if body.class_name is None:
                    user.student_profile.class_name = admin_class.class_code
            else:
                user.student_profile.admin_class_id = None
        if body.class_name is not None:
            user.student_profile.class_name = body.class_name.strip()
        if body.major is not None:
            user.student_profile.major = body.major.strip()
        if body.is_officer is not None:
            user.student_profile.is_officer = body.is_officer

    # Update TeacherProfile if teacher
    if user.teacher_profile:
        if body.department is not None:
            user.teacher_profile.department = body.department.strip()
        if body.academic_title is not None:
            user.teacher_profile.academic_title = body.academic_title.strip()
        if body.office_room is not None:
            user.teacher_profile.office_room = body.office_room.strip()

    await s.commit()
    await s.refresh(user)
    return serialize_admin_user(user)


@router.get("/class-names", response_model=List[str])
async def list_class_names(s: AsyncSession = Depends(get_db)):
    """Distinct class_name từ student_profiles cho dropdown tạo/sửa SV."""
    rows = (
        await s.execute(
            select(StudentProfile.class_name)
            .where(StudentProfile.class_name.is_not(None), StudentProfile.class_name != "")
            .distinct()
            .order_by(StudentProfile.class_name)
        )
    ).scalars().all()
    return [r for r in rows if r]


DEFAULT_STUDENT_PASSWORD = "123456"
STUDENT_IMPORT_HEADERS = ["Mã Sinh Viên", "Họ và Tên", "Email", "Lớp Sinh Hoạt", "Chuyên Ngành"]

# Alias header (đã chuẩn hoá: thường, bỏ dấu, chỉ giữ chữ+số) -> field.
_STUDENT_IMPORT_ALIASES: Dict[str, str] = {}
for _f, _aliases in {
    "user_code": ["masinhvien", "msv", "masv", "mssv", "studentcode", "usercode", "ma"],
    "full_name": ["hovaten", "hoten", "fullname", "ten", "studentname", "name"],
    "email": ["email", "mail", "thudientu"],
    "class_name": ["lopsinhhoat", "lop", "class", "classname", "lopsinhhoatlop"],
    "major": ["chuyennganh", "nganh", "major", "khoanganh"],
}.items():
    for _a in _aliases:
        _STUDENT_IMPORT_ALIASES[_a] = _f


def _norm_header(value: Any) -> str:
    """Chuẩn hoá tên cột: thường + bỏ dấu + chỉ giữ [a-z0-9]."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFD", str(value).strip().lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", text)


def _find_student_header_row(values_rows: List[List[Any]]) -> Optional[int]:
    """Tìm dòng header trong 10 dòng đầu (có mã SV + họ tên)."""
    for idx, row in enumerate(values_rows[:10]):
        fields = {_STUDENT_IMPORT_ALIASES.get(_norm_header(c)) for c in row}
        fields.discard(None)
        if {"user_code", "full_name"} <= fields:
            return idx
    return None


def _build_student_import_template() -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Sinh vien"
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    for col, h in enumerate(STUDENT_IMPORT_HEADERS, start=1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in [
        ("SV2026001", "Nguyễn Văn A", "sv2026001@student.edu.vn", "CNTT-K24A", "Kỹ thuật phần mềm"),
        ("SV2026002", "Trần Thị B", "", "CNTT-K24A", "Trí tuệ nhân tạo"),
    ]:
        ws.append(row)
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 32
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 26
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@router.get("/import-excel/template")
async def download_student_import_template():
    """Tải file mẫu nhập sinh viên (header chuẩn + 2 dòng ví dụ)."""
    return Response(
        content=_build_student_import_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="mau_nhap_sinh_vien.xlsx"'},
    )


@router.post("/import-excel")
async def import_students_excel(
    file: UploadFile = File(...),
    s: AsyncSession = Depends(get_db),
):
    """Nhập sinh viên hàng loạt từ file Excel (.xlsx).

    - Tự dò dòng header (alias Việt/Anh, không dấu vẫn nhận).
    - Mật khẩu mặc định `123456` cho mọi tài khoản tạo mới.
    - Email trống -> tự sinh `<mã-thường>@student.edu.vn`.
    - Dòng trùng mã/email (trong DB hoặc trong file) -> bỏ qua, ghi vào `errors`.
    """
    filename = (file.filename or "").lower()
    if not filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File phải có định dạng .xlsx (hoặc .xlsm)",
        )
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File rỗng")
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File vượt quá 10MB")
    try:
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
        ws = wb.active
        values_rows: List[List[Any]] = list(ws.iter_rows(values_only=True))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không đọc được file Excel")
    if not values_rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File Excel không có dữ liệu")
    header_idx = _find_student_header_row(values_rows)
    if header_idx is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không tìm thấy dòng tiêu đề (cần ít nhất cột Mã sinh viên + Họ tên)",
        )
    col_of: Dict[str, int] = {}
    for col, cell in enumerate(values_rows[header_idx]):
        field = _STUDENT_IMPORT_ALIASES.get(_norm_header(cell))
        if field and field not in col_of:
            col_of[field] = col
    try:
        role_obj = (await s.execute(select(Role).where(Role.role_name == "STUDENT"))).scalar_one_or_none()
    except Exception:
        role_obj = None
    if not role_obj:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Chưa có vai trò STUDENT trong hệ thống")
    try:
        from detect_ai.modules.academic.public import AdministrativeClass
        admin_classes = (await s.execute(select(AdministrativeClass))).scalars().all()
        admin_by_code = {c.class_code.strip().upper(): c.id for c in admin_classes}
    except Exception:
        admin_by_code = {}
    existing_codes = set((await s.execute(select(User.user_code))).scalars().all())
    existing_emails = {e.lower() for e in (await s.execute(select(User.email))).scalars().all()}
    seen_codes, seen_emails = set(), set()
    created, errors = 0, []
    EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    for offset, row in enumerate(values_rows[header_idx + 1:]):
        excel_row = header_idx + offset + 2  # số dòng Excel (1-based)
        get = lambda f: (str(row[col_of[f]]).strip() if f in col_of and row[col_of[f]] is not None else "")
        code = get("user_code").upper()
        name = get("full_name")
        email = get("email").lower()
        class_name = get("class_name").upper()
        major = get("major")
        if not code and not name and not email:
            continue  # bỏ dòng trống
        if not code or not name:
            errors.append({"row": excel_row, "user_code": code, "message": "Thiếu mã sinh viên hoặc họ tên"})
            continue
        if not email:
            email = f"{code.lower()}@student.edu.vn"
        if not EMAIL_RE.match(email):
            errors.append({"row": excel_row, "user_code": code, "message": f"Email '{email}' không hợp lệ"})
            continue
        if code in existing_codes or code in seen_codes:
            errors.append({"row": excel_row, "user_code": code, "message": f"Mã '{code}' đã tồn tại"})
            continue
        if email in existing_emails or email in seen_emails:
            errors.append({"row": excel_row, "user_code": code, "message": f"Email '{email}' đã tồn tại"})
            continue
        seen_codes.add(code)
        seen_emails.add(email)
        new_user = User(
            user_code=code,
            full_name=name,
            email=email,
            password_hash=get_password_hash(DEFAULT_STUDENT_PASSWORD),
            role_id=role_obj.id,
            is_active=True,
        )
        s.add(new_user)
        await s.flush()
        s.add(StudentProfile(
            user_id=new_user.id,
            admin_class_id=admin_by_code.get(class_name) if class_name else None,
            class_name=class_name,
            major=major,
            total_point=95,
            is_officer=False,
        ))
        created += 1
    await s.commit()
    return {"created": created, "skipped": len(errors), "errors": errors, "default_password": DEFAULT_STUDENT_PASSWORD}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    s: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    user = (await s.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng có ID {user_id}",
        )

    # Soft delete: set deleted_at to current timestamp
    from datetime import datetime, timezone
    user.deleted_at = datetime.now(timezone.utc)
    user.is_active = False
    await s.commit()
    return {"ok": True, "message": "User soft deleted successfully"}


@router.post("/{user_id}/avatar")
async def upload_user_avatar(
    user_id: int,
    photo: UploadFile = File(...),
    s: AsyncSession = Depends(get_db),
):
    """Upload ảnh chân dung cho người dùng (lưu avatar_url, không trích xuất khuôn mặt)."""
    stmt = (
        select(User)
        .options(selectinload(User.student_profile))
        .where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = (await s.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng có ID {user_id}",
        )

    img = await decode_upload(photo)
    avatar_url = await upload_avatar_image(user.user_code, img)
    if avatar_url:
        user.avatar_url = avatar_url

    await s.commit()

    face_status = "skipped"
    try:
        from detect_ai.modules.academic.public import ClassStudent
        from detect_ai.modules.recognition.public import (
            bump_db_version,
            bump_version,
            enroll_image as _enroll_image,
            get_engine,
        )

        async def _bump_gallery(uid: int) -> None:
            # Query academic nằm ở caller, không ở recognition infra.
            cids = (await s.execute(select(ClassStudent.class_id).where(
                ClassStudent.student_id == uid))).scalars().all()
            for cid in cids:
                bump_version(int(cid))  # RAM cục bộ thấy ngay
                await bump_db_version(s, int(cid))  # Postgres multi-worker; SQLite no-op

        await _enroll_image(s, user.id, img, source="avatar",
                            engine=get_engine("face"), on_enrolled=_bump_gallery)
        face_status = "enrolled"
    except Exception as e:  # noqa: BLE001
        face_status = f"no-face: {e}"

    return {
        "ok": True,
        "user_id": user_id,
        "avatar_url": user.avatar_url,
        "face_status": face_status,
    }


@router.post("/{user_id}/face-enroll")
async def face_enroll(
    user_id: int,
    photo: UploadFile = File(...),
    s: AsyncSession = Depends(get_db),
):
    """Admin ghi danh khuôn mặt từ ảnh chân dung (lưu vector vào face_embeddings)."""
    user = (
        await s.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng")
    img = await decode_upload(photo)
    prof = (
        await s.execute(select(StudentProfile).where(StudentProfile.user_id == user_id))
    ).scalar_one_or_none()
    if prof is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không có hồ sơ sinh viên")
    from detect_ai.modules.recognition.public import enroll_image as _enroll_image
    from detect_ai.modules.recognition.public import get_engine

    try:
        await _enroll_image(s, user_id, img, source="avatar", engine=get_engine("face"))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return {"face_enrolled": True, "user_id": user_id}

from __future__ import annotations
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
import numpy as np
import cv2
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..ai.pipeline import get_shared_models
from ..core.config import PHOTO_DIR
from ..core.deps import get_db
from ..models.student import Student
from ..streamers import face_store
from .files import decode_upload, safe_file
from .schemas import StudentPage

router = APIRouter(prefix="/api/students", tags=["students"])

@router.get("", response_model=StudentPage)
async def list_students(page: int = 1, size: int = 50, q: str = "",
                        s: AsyncSession = Depends(get_db)):
    # phan trang + tim kiem: thay tra het 1 lan cu (chet khi 1000 SV)
    stmt = select(Student)
    if q:
        stmt = stmt.where(Student.code.ilike(f"%{q}%") | Student.name.ilike(f"%{q}%"))
    total = (await s.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    rows = (await s.execute(stmt.order_by(Student.id.desc())
                            .offset((page - 1) * size).limit(size))).scalars().all()
    return {"items": [{"id": r.id, "code": r.code, "name": r.name, "class_name": r.class_name,
                         "photo": r.photo} for r in rows],
            "total": total, "page": page, "size": size}

@router.post("")
async def add_student(code: str = Form(...), name: str = Form(...),
                      class_name: str = Form(""), photo: UploadFile = File(...),
                      s: AsyncSession = Depends(get_db)):
    if not code.strip() or not name.strip():
        raise HTTPException(422, "thieu code/name")
    if (await s.execute(select(Student).where(Student.code == code))).scalar_one_or_none():
        raise HTTPException(409, "trung ma SV")
    img = await decode_upload(photo)
    v = get_shared_models()[1].embed(img, check_liveness=False)
    if v is None:
        raise HTTPException(422, "khong_tim_thay_khuon_mat")
    fn = f"{code.strip()}.jpg"
    cv2.imwrite(str(PHOTO_DIR / fn), img)
    s.add(Student(code=code, name=name, class_name=class_name,
                  embedding=np.asarray(v, dtype=np.float32).tobytes(), photo=fn))
    await s.commit()
    await face_store.reload()  # them SV xong index RAM cap nhat ngay, khoi restart
    return {"ok": True, "code": code}

@router.put("/{sid}")
async def update_student(sid: int, name: str = Form(...), class_name: str = Form(""),
                         photo: UploadFile | None = File(None),
                         s: AsyncSession = Depends(get_db)):
    # code khoa: doi code lam orphan attendance + lech ten file anh
    r = await s.get(Student, sid)
    if not r:
        raise HTTPException(404, "not found")
    if not name.strip():
        raise HTTPException(422, "thieu name")
    r.name = name
    r.class_name = class_name
    if photo is not None:
        img = await decode_upload(photo)
        v = get_shared_models()[1].embed(img, check_liveness=False)
        if v is None:
            raise HTTPException(422, "khong_tim_thay_khuon_mat")
        fn = f"{r.code.strip()}.jpg"
        cv2.imwrite(str(PHOTO_DIR / fn), img)
        r.embedding = np.asarray(v, dtype=np.float32).tobytes()
        r.photo = fn
    await s.commit()
    await face_store.reload()
    return {"ok": True}

@router.delete("/{sid}")
async def delete_student(sid: int, s: AsyncSession = Depends(get_db)):
    r = await s.get(Student, sid)
    if not r:
        raise HTTPException(404, "not found")
    if r.photo and "/" not in r.photo and "\\" not in r.photo:
        (PHOTO_DIR / r.photo).unlink(missing_ok=True)
    await s.delete(r)
    await s.commit()
    await face_store.reload()
    return {"ok": True}

@router.get("/photo/{name}")
async def photo(name: str):
    return FileResponse(safe_file(PHOTO_DIR, name))

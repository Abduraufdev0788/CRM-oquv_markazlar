"""
Students CRUD API — /api/v1/students/
"""
import uuid
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.student import Student, StudentStatus
from app.core.dependencies import get_current_active_user, require_roles
from app.models.user import User, UserRole

router = APIRouter(prefix="/students", tags=["Students"])

AnyStaff = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TEACHER))
ManagerOrAdmin = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))


@router.get("/", summary="O'quvchilar ro'yxati")
async def list_students(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    status: Optional[StudentStatus] = Query(None),
    search: Optional[str] = Query(None, description="Ism yoki telefon bo'yicha qidirish"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(Student)
    if status:
        query = query.where(Student.status == status)
    if search:
        query = query.where(
            Student.full_name.ilike(f"%{search}%") | Student.phone.ilike(f"%{search}%")
        )
    query = query.offset(skip).limit(limit).order_by(Student.created_at.desc())
    result = await db.execute(query)
    students = result.scalars().all()
    return {"data": students, "count": len(students)}


@router.get("/{student_id}", summary="O'quvchi profili")
async def get_student(
    student_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")
    return student


@router.post("/", status_code=status.HTTP_201_CREATED, summary="Yangi o'quvchi qo'shish")
async def create_student(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    student = Student(**data)
    db.add(student)
    await db.flush()
    return student


@router.put("/{student_id}", summary="O'quvchi ma'lumotlarini yangilash")
async def update_student(
    student_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")
    for key, value in data.items():
        if hasattr(student, key):
            setattr(student, key, value)
    return student


@router.delete("/{student_id}", summary="O'quvchini o'chirish (soft delete)")
async def delete_student(
    student_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")
    student.status = StudentStatus.EXPELLED
    return {"detail": "O'quvchi o'chirildi (status: expelled)"}

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
from app.schemas import (
    StudentCreate, StudentUpdate, StudentResponse,
    StudentBriefResponse, PaginatedResponse, MessageResponse,
)

router = APIRouter(prefix="/students", tags=["Students"])

AnyStaff = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TEACHER))
ManagerOrAdmin = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
AdminOnly = Depends(require_roles(UserRole.ADMIN))


@router.get(
    "/",
    response_model=PaginatedResponse[StudentBriefResponse],
    summary="O'quvchilar ro'yxati (filter + pagination)",
)
async def list_students(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    student_status: Optional[StudentStatus] = Query(None, alias="status"),
    search: Optional[str] = Query(None, description="Ism yoki telefon bo'yicha qidirish"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(Student)
    if student_status:
        query = query.where(Student.status == student_status)
    if search:
        query = query.where(
            Student.full_name.ilike(f"%{search}%") | Student.phone.ilike(f"%{search}%")
        )

    # Total count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Data
    data_q = query.offset(skip).limit(limit).order_by(Student.created_at.desc())
    students = (await db.execute(data_q)).scalars().all()

    return PaginatedResponse.create(data=students, total=total, skip=skip, limit=limit)


@router.get(
    "/{student_id}",
    response_model=StudentResponse,
    summary="O'quvchi to'liq profili (parent nested)",
)
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


@router.post(
    "/",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yangi o'quvchi qo'shish",
)
async def create_student(
    data: StudentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    # Telefon raqam takrorlanmasligini tekshirish
    if data.phone:
        exists = (await db.execute(
            select(Student).where(Student.phone == data.phone)
        )).scalar_one_or_none()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu telefon raqam allaqachon ro'yxatdan o'tgan",
            )

    student = Student(**data.model_dump())
    db.add(student)
    await db.flush()
    await db.refresh(student)
    return student


@router.put(
    "/{student_id}",
    response_model=StudentResponse,
    summary="O'quvchi ma'lumotlarini yangilash",
)
async def update_student(
    student_id: uuid.UUID,
    data: StudentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")

    # Faqat yuborilgan maydonlarni yangilash (PATCH uslubi)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(student, key, value)

    await db.flush()
    await db.refresh(student)
    return student


@router.delete(
    "/{student_id}",
    response_model=MessageResponse,
    summary="O'quvchini o'chirish (soft delete — status EXPELLED ga o'tadi)",
)
async def delete_student(
    student_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")

    student.status = StudentStatus.EXPELLED
    return MessageResponse(detail=f"{student.full_name} o'chirildi (status: expelled)")

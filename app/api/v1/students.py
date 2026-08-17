"""
Students CRUD API — /api/v1/students/
"""
import uuid
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.student import Student, StudentStatus
from app.core.dependencies import get_current_active_user, require_roles
from app.models.user import User, UserRole
from app.models.academic import Enrollment, EnrollmentStatus
from app.schemas import (
    StudentCreate, StudentUpdate, StudentResponse,
    StudentBriefResponse, PaginatedResponse, MessageResponse,
    EnrollmentResponse
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
    limit: int = Query(20, ge=1, le=10000),
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
    result = await db.execute(
        select(Student)
        .options(selectinload(Student.parent))
        .where(Student.id == student_id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")
    return student


@router.get(
    "/{student_id}/enrollments",
    response_model=list[EnrollmentResponse],
    summary="O'quvchining barcha guruhlarini (enrollments) olish",
)
async def get_student_enrollments(
    student_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    from sqlalchemy.orm import selectinload
    from app.models.academic import Group, EnrollmentStatus
    
    query = (
        select(Enrollment)
        .options(
            selectinload(Enrollment.group).selectinload(Group.room),
            selectinload(Enrollment.group).selectinload(Group.course),
            selectinload(Enrollment.student)
        )
        .where(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatus.ACTIVE
        )
        .order_by(Enrollment.enrolled_at.desc())
    )
    enrollments = (await db.execute(query)).scalars().all()
    return enrollments


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

    # Ota-onani tekshirish yoki yaratish
    parent_id = data.parent_id
    if not parent_id and data.parent_phone and data.parent_name:
        from app.models.student import Parent
        parent = (await db.execute(
            select(Parent).where(Parent.phone == data.parent_phone)
        )).scalar_one_or_none()

        if not parent:
            parent = Parent(
                full_name=data.parent_name,
                phone=data.parent_phone,
            )
            db.add(parent)
            await db.flush()
            await db.refresh(parent)
        
        parent_id = parent.id

    student_dict = data.model_dump(exclude={"parent_name", "parent_phone"})
    student_dict["parent_id"] = parent_id

    student = Student(**student_dict)
    db.add(student)
    await db.flush()

    student = (await db.execute(
        select(Student)
        .options(selectinload(Student.parent))
        .where(Student.id == student.id)
    )).scalar_one()
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

    # Ota-onani tekshirish yoki yaratish
    if "parent_phone" in update_data and "parent_name" in update_data:
        parent_phone = update_data.pop("parent_phone")
        parent_name = update_data.pop("parent_name")
        
        if parent_phone and parent_name:
            from app.models.student import Parent
            parent = (await db.execute(
                select(Parent).where(Parent.phone == parent_phone)
            )).scalar_one_or_none()

            if parent:
                parent.full_name = parent_name
            else:
                parent = Parent(
                    full_name=parent_name,
                    phone=parent_phone,
                )
                db.add(parent)
                await db.flush()
                await db.refresh(parent)
            
            update_data["parent_id"] = parent.id
            
    # Agar biri bo'lib boshqasi bo'lmasa yoki update_data da qolib ketgan bo'lsa o'chirish
    update_data.pop("parent_phone", None)
    update_data.pop("parent_name", None)

    for key, value in update_data.items():
        setattr(student, key, value)

    await db.flush()
    
    student = (await db.execute(
        select(Student)
        .options(selectinload(Student.parent))
        .where(Student.id == student_id)
    )).scalar_one()
    return student


@router.delete(
    "/{student_id}",
    response_model=MessageResponse,
    summary="O'quvchini o'chirish (soft delete — status EXPELLED ga o'tadi)",
)
async def delete_student(
    student_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")

    student.status = StudentStatus.EXPELLED
    
    # Guruhlardan chiqarish (barcha aktiv yozuvlarni DROPPED ga o'tkazish)
    enrollments = (await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatus.ACTIVE
        )
    )).scalars().all()
    
    for enr in enrollments:
        enr.status = EnrollmentStatus.DROPPED

    await db.flush()
    return MessageResponse(detail=f"{student.full_name} o'chirildi va guruhlardan chiqarildi")

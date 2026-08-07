"""
Parents CRUD API — /api/v1/parents/
"""
import uuid
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User, UserRole
from app.models.student import Parent
from app.core.dependencies import require_roles
from app.schemas import (
    ParentCreate, ParentUpdate, ParentResponse, ParentBriefResponse,
    PaginatedResponse, MessageResponse,
)

router = APIRouter(prefix="/parents", tags=["Parents (Ota-onalar)"])

AnyStaff = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
AdminOnly = Depends(require_roles(UserRole.ADMIN))


@router.get("/", response_model=PaginatedResponse[ParentBriefResponse], summary="Ota-onalar ro'yxati")
async def list_parents(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    search: Optional[str] = Query(None, description="Ism yoki telefon bo'yicha"),
    has_telegram: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(Parent)
    if search:
        query = query.where(
            Parent.full_name.ilike(f"%{search}%") | Parent.phone.ilike(f"%{search}%")
        )
    if has_telegram is True:
        query = query.where(Parent.telegram_id.isnot(None))
    elif has_telegram is False:
        query = query.where(Parent.telegram_id.is_(None))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    parents = (await db.execute(query.offset(skip).limit(limit).order_by(Parent.created_at.desc()))).scalars().all()
    return PaginatedResponse.create(data=parents, total=total, skip=skip, limit=limit)


@router.get("/{parent_id}", response_model=ParentResponse, summary="Ota-ona ma'lumoti")
async def get_parent(
    parent_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    parent = (await db.execute(select(Parent).where(Parent.id == parent_id))).scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail="Ota-ona topilmadi")
    return parent


@router.post("/", response_model=ParentResponse, status_code=201, summary="Yangi ota-ona qo'shish")
async def create_parent(
    data: ParentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    existing = (await db.execute(select(Parent).where(Parent.phone == data.phone))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Bu telefon raqam allaqachon mavjud")

    parent = Parent(**data.model_dump())
    db.add(parent)
    await db.flush()
    await db.refresh(parent)
    return parent


@router.put("/{parent_id}", response_model=ParentResponse, summary="Ota-ona ma'lumotlarini yangilash")
async def update_parent(
    parent_id: uuid.UUID,
    data: ParentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    parent = (await db.execute(select(Parent).where(Parent.id == parent_id))).scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail="Ota-ona topilmadi")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(parent, key, value)
    await db.flush()
    await db.refresh(parent)
    return parent


@router.delete("/{parent_id}", response_model=MessageResponse, summary="Ota-onani o'chirish")
async def delete_parent(
    parent_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    parent = (await db.execute(select(Parent).where(Parent.id == parent_id))).scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail="Ota-ona topilmadi")

    # Farzandlari borligini tekshirish
    from app.models.student import Student
    children_count = (await db.execute(
        select(func.count(Student.id)).where(Student.parent_id == parent_id)
    )).scalar_one()
    if children_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Bu ota-onaning {children_count} ta farzandi mavjud. Avval farzandlarini ajrating.",
        )

    await db.delete(parent)
    return MessageResponse(detail="Ota-ona o'chirildi")

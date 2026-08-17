"""
Users (Xodimlar) CRUD API — /api/v1/users/
Faqat ADMIN boshqara oladi.
"""
import uuid
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.core.dependencies import require_roles
from app.core.audit import write_audit_log
from app.models.system import AuditAction
from app.schemas import (
    UserCreate, UserUpdate, PasswordChange,
    UserResponse, UserBriefResponse,
    PaginatedResponse, MessageResponse,
)

router = APIRouter(prefix="/users", tags=["Users (Xodimlar)"])

AdminOnly = Depends(require_roles(UserRole.ADMIN))
AnyStaff = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))


@router.get(
    "/",
    response_model=PaginatedResponse[UserBriefResponse],
    summary="Barcha xodimlar ro'yxati",
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Ism yoki telefon"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=10000),
):
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if search:
        query = query.where(
            User.full_name.ilike(f"%{search}%") | User.phone.ilike(f"%{search}%")
        )

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    users = (await db.execute(query.offset(skip).limit(limit).order_by(User.created_at.desc()))).scalars().all()

    return PaginatedResponse.create(data=users, total=total, skip=skip, limit=limit)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Xodim to'liq ma'lumoti",
)
async def get_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Xodim topilmadi")
    return user


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yangi xodim qo'shish (faqat Admin)",
)
async def create_user(
    data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    # Telefon va email takrorlanmasligini tekshirish
    existing = (await db.execute(
        select(User).where(User.phone == data.phone)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Bu telefon raqam allaqachon mavjud")

    user = User(
        full_name=data.full_name,
        phone=data.phone,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.flush()

    await write_audit_log(
        db, action=AuditAction.CREATE, table_name="users",
        user_id=current_user.id, record_id=user.id,
        new_values={"full_name": user.full_name, "role": user.role},
    )

    await db.refresh(user)
    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Xodim ma'lumotlarini yangilash",
)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Xodim topilmadi")

    old_values = {"full_name": user.full_name, "role": user.role, "is_active": user.is_active}
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    await write_audit_log(
        db, action=AuditAction.UPDATE, table_name="users",
        user_id=current_user.id, record_id=user.id,
        old_values=old_values, new_values=update_data,
    )

    await db.flush()
    await db.refresh(user)
    return user


@router.post(
    "/{user_id}/change-password",
    response_model=MessageResponse,
    summary="Parol almashtirish",
)
async def change_password(
    user_id: uuid.UUID,
    data: PasswordChange,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TEACHER))],
):
    # O'zi yoki Admin o'zgartira oladi
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Faqat o'z parolingizni o'zgartira olasiz")

    from app.core.security import verify_password
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Xodim topilmadi")

    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Joriy parol noto'g'ri")

    user.password_hash = hash_password(data.new_password)
    return MessageResponse(detail="Parol muvaffaqiyatli o'zgartirildi")


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Xodimni deaktivatsiya qilish (soft delete)",
)
async def deactivate_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="O'zingizni o'chira olmaysiz")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Xodim topilmadi")

    user.is_active = False
    await write_audit_log(
        db, action=AuditAction.DELETE, table_name="users",
        user_id=current_user.id, record_id=user.id,
        description=f"{user.full_name} deactivated",
    )
    return MessageResponse(detail=f"{user.full_name} deaktiv qilindi")

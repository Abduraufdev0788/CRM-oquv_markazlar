from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone, timedelta
from typing import Annotated

from app.database import get_db
from app.models.user import User, RefreshToken
from app.models.student import Student, StudentStatus
from app.core.security import (
    verify_password, create_access_token,
    create_refresh_token, hash_token
)
from app.core.dependencies import get_current_active_user
from app.core.audit import write_audit_log
from app.models.system import AuditAction
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", summary="Tizimga kirish — Access + Refresh token olish")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Foydalanuvchini phone bo'yicha topish
    result = await db.execute(
        select(User).where(User.phone == form_data.username, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telefon raqam yoki parol noto'g'ri",
        )

    # Tokenlar yaratish
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    raw_refresh, refresh_hash = create_refresh_token()

    # Refresh tokenni bazaga saqlash
    db_refresh = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        device_info=request.headers.get("User-Agent", "")[:255],
        ip_address=request.client.host if request.client else None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(db_refresh)

    # last_login yangilash
    user.last_login = datetime.now(timezone.utc)

    await write_audit_log(
        db, action=AuditAction.LOGIN, table_name="users",
        user_id=user.id, ip_address=request.client.host if request.client else None
    )

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "role": user.role,
    }


@router.post("/student-login", summary="O'quvchi kabinetiga kirish")
async def student_login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # O'quvchi form_data.username ga o'z telefonini kiritadi
    result = await db.execute(
        select(Student).where(Student.phone == form_data.username, Student.status == StudentStatus.ACTIVE)
    )
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telefon raqam xato",
        )

    # Parol mantiqini tekshirish
    if student.password_hash:
        # Agar yangi parol o'rnatilgan bo'lsa
        if not verify_password(form_data.password, student.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Parol noto'g'ri",
            )
    else:
        # Eski usul (Tug'ilgan sana) bilan tekshirish
        valid_passwords = ["123456"]
        if student.birth_date:
            valid_passwords.append(student.birth_date.strftime("%Y-%m-%d"))
            valid_passwords.append(student.birth_date.strftime("%d%m%Y"))
            valid_passwords.append(student.birth_date.strftime("%d.%m.%Y"))

        if form_data.password not in valid_passwords:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Parol (Tug'ilgan sana) noto'g'ri. Masalan: 2005-10-15 yoki 15102005",
            )

    # JWT token yaratamiz, role="student" qilib belgilaymiz
    access_token = create_access_token(data={"sub": str(student.id), "role": "student"})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": "student",
    }


@router.post("/refresh", summary="Access tokenni yangilash")
async def refresh_token(
    raw_token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    db_token = result.scalar_one_or_none()

    if not db_token:
        raise HTTPException(status_code=401, detail="Refresh token noto'g'ri yoki muddati o'tgan")

    # Eski tokenni bekor qilish (rotation)
    db_token.is_revoked = True

    # Yangi tokenlar
    result = await db.execute(select(User).where(User.id == db_token.user_id))
    user = result.scalar_one()

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    raw_refresh, refresh_hash = create_refresh_token()

    new_refresh = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_refresh)

    return {"access_token": access_token, "refresh_token": raw_refresh, "token_type": "bearer"}


@router.post("/logout", summary="Tizimdan chiqish")
async def logout(
    raw_token: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == current_user.id,
        )
    )
    db_token = result.scalar_one_or_none()
    if db_token:
        db_token.is_revoked = True

    await write_audit_log(db, action=AuditAction.LOGOUT, table_name="users", user_id=current_user.id)
    return {"detail": "Muvaffaqiyatli chiqildi"}


@router.get("/me", summary="Joriy foydalanuvchi ma'lumotlari")
async def get_me(current_user: Annotated[User, Depends(get_current_active_user)]):
    return {
        "id": str(current_user.id),
        "full_name": current_user.full_name,
        "phone": current_user.phone,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "photo_url": current_user.photo_url,
    }


from pydantic import BaseModel
from typing import Optional

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    photo_url: Optional[str] = None

class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str

@router.put("/me/profile", summary="Profilni tahrirlash")
async def update_profile(
    data: ProfileUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.photo_url is not None:
        current_user.photo_url = data.photo_url
        
    await db.commit()
    return {"detail": "Profil muvaffaqiyatli yangilandi"}

@router.put("/me/password", summary="Parolni o'zgartirish")
async def update_password(
    data: PasswordUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Eski parol noto'g'ri")
        
    from app.core.security import get_password_hash
    current_user.password_hash = get_password_hash(data.new_password)
    await db.commit()
    
    return {"detail": "Parol muvaffaqiyatli o'zgartirildi"}

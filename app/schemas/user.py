"""
User & Auth schemas — Xodimlar va autentifikatsiya.
"""
import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import field_validator, EmailStr, Field

from app.schemas.base import BaseSchema, BaseResponse
from app.models.user import UserRole


# ── Validators ─────────────────────────────────────────────────────────────────
def validate_phone(v: str) -> str:
    """O'zbek telefon raqamini tekshirish: +998XXXXXXXXX"""
    pattern = r"^\+998[0-9]{9}$"
    if not re.match(pattern, v):
        raise ValueError("Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak")
    return v


def validate_password(v: str) -> str:
    """Kamida 8 ta belgi, bitta raqam bo'lishi shart."""
    if len(v) < 8:
        raise ValueError("Parol kamida 8 ta belgidan iborat bo'lishi kerak")
    if not any(c.isdigit() for c in v):
        raise ValueError("Parolda kamida bitta raqam bo'lishi kerak")
    return v


# ── Auth Schemas ───────────────────────────────────────────────────────────────
class TokenResponse(BaseSchema):
    """Login muvaffaqiyatli bo'lganda qaytariladigan tokenlar."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: UserRole


class RefreshRequest(BaseSchema):
    raw_token: str = Field(..., description="Refresh token (raw, hash emas)")


class LogoutRequest(BaseSchema):
    raw_token: str


# ── User Schemas ───────────────────────────────────────────────────────────────
class UserCreate(BaseSchema):
    """Yangi xodim yaratish."""
    full_name: str = Field(..., min_length=2, max_length=100, examples=["Ali Valiyev"])
    phone: str = Field(..., examples=["+998901234567"])
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.TEACHER

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: str) -> str:
        return validate_phone(v)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password(v)


class UserUpdate(BaseSchema):
    """Xodim ma'lumotlarini yangilash — barcha maydon ixtiyoriy."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    photo_url: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None


class PasswordChange(BaseSchema):
    """Parol almashtirish."""
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password(v)


class UserResponse(BaseResponse):
    """Xodim ma'lumotlarini qaytarish (parol va hash ko'rsatilmaydi)."""
    full_name: str
    phone: str
    email: Optional[str]
    role: UserRole
    is_active: bool
    photo_url: Optional[str]
    last_login: Optional[datetime]


class UserBriefResponse(BaseSchema):
    """Boshqa entitylarda nested ko'rinishda ishlatish uchun qisqa variant."""
    id: uuid.UUID
    full_name: str
    phone: str
    role: UserRole
    is_active: bool

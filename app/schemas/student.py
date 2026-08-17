"""
Student & Parent schemas — O'quvchilar va ota-onalar.
"""
import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List
from pydantic import field_validator, Field, model_validator

from app.schemas.base import BaseSchema, BaseResponse
from app.models.student import StudentStatus


def validate_phone_optional(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    pattern = r"^\+998[0-9]{9}$"
    if not re.match(pattern, v):
        raise ValueError("Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak")
    return v


# ── Parent Schemas ─────────────────────────────────────────────────────────────
class ParentCreate(BaseSchema):
    full_name: str = Field(..., min_length=2, max_length=100, examples=["Nodira Karimova"])
    phone: str = Field(..., examples=["+998901234567"])
    telegram_id: Optional[int] = Field(None, description="Telegram foydalanuvchi ID (bot uchun)")
    notes: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: str) -> str:
        pattern = r"^\+998[0-9]{9}$"
        if not re.match(pattern, v):
            raise ValueError("Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak")
        return v


class ParentUpdate(BaseSchema):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = None
    telegram_id: Optional[int] = None
    is_bot_active: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone_optional(v)


class ParentResponse(BaseResponse):
    full_name: str
    phone: str
    telegram_id: Optional[int]
    is_bot_active: bool
    notes: Optional[str]


class ParentBriefResponse(BaseSchema):
    id: uuid.UUID
    full_name: str
    phone: str
    telegram_id: Optional[int]


# ── Student Schemas ────────────────────────────────────────────────────────────
class StudentCreate(BaseSchema):
    full_name: str = Field(..., min_length=2, max_length=100, examples=["Jasur Toshmatov"])
    phone: Optional[str] = Field(None, examples=["+998911234567"])
    birth_date: Optional[date] = Field(None, examples=["2008-05-15"])
    photo_url: Optional[str] = Field(None, max_length=255)
    parent_id: Optional[uuid.UUID] = None
    parent_name: Optional[str] = Field(None, max_length=100, description="Ota-ona ismi")
    parent_phone: Optional[str] = Field(None, examples=["+998901234567"], description="Ota-ona telefon raqami")
    face_data_id: Optional[str] = Field(
        None, max_length=100, description="Face ID qurilmadan olingan shaxs ID"
    )
    notes: Optional[str] = None

    @field_validator("phone", "parent_phone")
    @classmethod
    def phone_format(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone_optional(v)

    @field_validator("birth_date")
    @classmethod
    def birth_date_valid(cls, v: Optional[date]) -> Optional[date]:
        if v and v >= date.today():
            raise ValueError("Tug'ilgan sana kelajakda bo'lishi mumkin emas")
        return v


class StudentUpdate(BaseSchema):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    photo_url: Optional[str] = Field(None, max_length=255)
    parent_id: Optional[uuid.UUID] = None
    parent_name: Optional[str] = Field(None, max_length=100)
    parent_phone: Optional[str] = None
    status: Optional[StudentStatus] = None
    face_data_id: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None

    @field_validator("phone", "parent_phone")
    @classmethod
    def phone_format(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone_optional(v)


class StudentResponse(BaseResponse):
    """To'liq o'quvchi profili."""
    full_name: str
    phone: Optional[str]
    birth_date: Optional[date]
    photo_url: Optional[str]
    parent_id: Optional[uuid.UUID]
    status: StudentStatus
    balance: Decimal
    face_data_id: Optional[str]
    notes: Optional[str]
    # Nested
    parent: Optional[ParentBriefResponse] = None


class StudentBriefResponse(BaseSchema):
    """Ro'yxat va nested uchun qisqa variant."""
    id: uuid.UUID
    full_name: str
    phone: Optional[str]
    birth_date: Optional[date] = None
    status: StudentStatus
    balance: Decimal


class StudentBalanceResponse(BaseSchema):
    """O'quvchi balansini qaytarish."""
    student_id: uuid.UUID
    full_name: str
    balance: Decimal

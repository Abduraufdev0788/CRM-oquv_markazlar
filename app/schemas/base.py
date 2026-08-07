"""
Base schemas — barcha sxemalar shu yerdan meros oladi.
"""
import uuid
from datetime import datetime
from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    """ORM modellarini o'qish uchun from_attributes=True."""
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class BaseResponse(BaseSchema):
    """Har bir response sxemasida id, created_at, updated_at bo'ladi."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Sahifalangan javob uchun umumiy wrapper.
    Ishlatish: PaginatedResponse[StudentResponse]
    """
    data: List[T]
    total: int
    skip: int
    limit: int
    has_next: bool

    @classmethod
    def create(cls, data: List[T], total: int, skip: int, limit: int) -> "PaginatedResponse[T]":
        return cls(
            data=data,
            total=total,
            skip=skip,
            limit=limit,
            has_next=(skip + limit) < total,
        )


class MessageResponse(BaseModel):
    """Oddiy xabar qaytarish uchun."""
    detail: str

"""
System schemas — Notification, AuditLog.
"""
import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import Field

from app.schemas.base import BaseSchema, BaseResponse
from app.models.system import (
    NotificationChannel, NotificationStatus, NotificationType,
    AuditAction
)


# ── Notification Schemas ───────────────────────────────────────────────────────
class NotificationCreate(BaseSchema):
    """Yangi xabarnoma yaratish (odatda service tomonidan chaqiriladi)."""
    parent_id: Optional[uuid.UUID] = None
    student_id: Optional[uuid.UUID] = None
    channel: NotificationChannel
    notif_type: NotificationType
    title: str = Field(..., max_length=200)
    body: str = Field(..., min_length=1)


class NotificationResponse(BaseResponse):
    parent_id: Optional[uuid.UUID]
    student_id: Optional[uuid.UUID]
    channel: NotificationChannel
    notif_type: NotificationType
    title: str
    body: str
    status: NotificationStatus
    sent_at: Optional[datetime]
    error_message: Optional[str]
    external_id: Optional[str]


# ── AuditLog Schemas ───────────────────────────────────────────────────────────
class AuditLogResponse(BaseResponse):
    """AuditLog faqat o'qish uchun — yozish faqat system orqali."""
    user_id: Optional[uuid.UUID]
    action: AuditAction
    table_name: str
    record_id: Optional[uuid.UUID]
    old_values: Optional[Any]
    new_values: Optional[Any]
    ip_address: Optional[str]
    description: Optional[str]


class AuditLogFilter(BaseSchema):
    """AuditLog filtrlash parametrlari."""
    user_id: Optional[uuid.UUID] = None
    action: Optional[AuditAction] = None
    table_name: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

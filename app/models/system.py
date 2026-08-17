import uuid
import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, Enum as SAEnum, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.student import Student, Parent


class NotificationChannel(str, enum.Enum):
    TELEGRAM = "telegram"
    SMS = "sms"
    EMAIL = "email"
    IN_APP = "in_app"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationType(str, enum.Enum):
    ATTENDANCE = "attendance"
    PAYMENT_DUE = "payment_due"
    PAYMENT_RECEIVED = "payment_received"
    GRADE = "grade"
    GENERAL = "general"
    SYSTEM_ALERT = "system_alert"


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"


class Notification(BaseModel):
    __tablename__ = "notifications"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("parents.id"), nullable=True, index=True
    )
    student_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        SAEnum(NotificationChannel, name="notificationchannel"), nullable=False
    )
    notif_type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notificationtype"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        SAEnum(NotificationStatus, name="notificationstatus"),
        nullable=False, default=NotificationStatus.PENDING, index=True
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    parent: Mapped[Optional["Parent"]] = relationship()
    student: Mapped[Optional["Student"]] = relationship(back_populates="notifications")


class AuditLog(BaseModel):
    """
    Immutable log — bu jadvalga UPDATE va DELETE ta'qiqlangan.
    Faqat INSERT va SELECT ruxsat etiladi.
    """
    __tablename__ = "audit_logs"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, name="auditaction"), nullable=False
    )
    table_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    record_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    old_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")

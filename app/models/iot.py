import uuid
import enum
from datetime import datetime, time
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import (
    String, Boolean, SmallInteger, Text,
    Enum as SAEnum, ForeignKey, DateTime, Time, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.student import Student
    from app.models.lesson import Lesson
    from app.models.user import User


class DeviceStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class FaceDevice(BaseModel):
    __tablename__ = "face_devices"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), unique=True, nullable=False)
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[DeviceStatus] = mapped_column(
        SAEnum(DeviceStatus, name="devicestatus"),
        nullable=False, default=DeviceStatus.OFFLINE, index=True
    )
    last_ping: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    api_secret: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    face_logs: Mapped[List["FaceLog"]] = relationship(back_populates="device")


class FaceLog(BaseModel):
    __tablename__ = "face_logs"

    device_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("face_devices.id"), nullable=False, index=True
    )
    face_data_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    device: Mapped["FaceDevice"] = relationship(back_populates="face_logs")
    # Student FK yo'q — face_data_id (string) orqali bog'lanadi, shuning uchun viewonly
    student: Mapped[Optional["Student"]] = relationship(
        "Student",
        primaryjoin="foreign(FaceLog.face_data_id) == Student.face_data_id",
        viewonly=True,
    )
    attendance: Mapped[Optional["Attendance"]] = relationship(back_populates="face_log")


class Attendance(BaseModel):
    __tablename__ = "attendances"

    __table_args__ = (
        UniqueConstraint("student_id", "lesson_id", name="uq_attendance_student_lesson"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=False, index=True
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        SAEnum(AttendanceStatus, name="attendancestatus"), nullable=False, index=True
    )
    check_in_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    late_minutes: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    face_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("face_logs.id"), nullable=True
    )
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    manual_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped["Student"] = relationship()
    lesson: Mapped["Lesson"] = relationship(back_populates="attendances")
    face_log: Mapped[Optional["FaceLog"]] = relationship(back_populates="attendance")

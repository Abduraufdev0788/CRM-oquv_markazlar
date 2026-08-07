"""
IoT & Attendance schemas — FaceDevice, FaceLog, Attendance.
"""
import uuid
import re
from datetime import datetime, time
from typing import Optional, Any
from pydantic import field_validator, Field

from app.schemas.base import BaseSchema, BaseResponse
from app.models.iot import DeviceStatus, AttendanceStatus


# ── FaceDevice Schemas ─────────────────────────────────────────────────────────
class FaceDeviceCreate(BaseSchema):
    name: str = Field(..., min_length=2, max_length=100, examples=["Kirish eshigi"])
    ip_address: str = Field(..., examples=["192.168.1.100"])
    serial_number: str = Field(..., min_length=3, max_length=100, examples=["FD-2024-001"])
    location: Optional[str] = Field(None, max_length=200, examples=["1-qavat, xona 101"])
    api_secret: str = Field(..., min_length=16, max_length=255)

    @field_validator("ip_address")
    @classmethod
    def valid_ip(cls, v: str) -> str:
        # IPv4 yoki IPv6
        ipv4 = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
        if not ipv4.match(v):
            raise ValueError("IP manzil noto'g'ri formatda (masalan: 192.168.1.100)")
        parts = v.split(".")
        if not all(0 <= int(p) <= 255 for p in parts):
            raise ValueError("IP manzil oktetlari 0-255 oralig'ida bo'lishi kerak")
        return v


class FaceDeviceUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    location: Optional[str] = None
    status: Optional[DeviceStatus] = None


class FaceDeviceResponse(BaseResponse):
    name: str
    ip_address: str
    serial_number: str
    location: Optional[str]
    status: DeviceStatus
    last_ping: Optional[datetime]
    # api_secret ko'rsatilmaydi — xavfsizlik uchun


# ── FaceLog Schemas ────────────────────────────────────────────────────────────
class FaceWebhookPayload(BaseSchema):
    """
    Face ID qurilmadan keladigan webhook payload.
    Har bir qurilma ishlab chiqaruvchisi o'z formatida yuborishi mumkin,
    shuning uchun raw_payload ni JSONB da saqlaymiz.
    """
    face_id: str = Field(..., description="Qurilmadagi shaxs ID")
    timestamp: str = Field(..., description="ISO 8601 format: 2024-08-07T09:05:00")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Aniqlash darajasi (0-1)")
    device_serial: Optional[str] = None
    extra: Optional[dict] = None  # Qurilmaga xos qo'shimcha ma'lumotlar


class FaceLogResponse(BaseResponse):
    device_id: uuid.UUID
    face_data_id: str
    raw_payload: Any
    logged_at: datetime
    received_at: datetime
    is_processed: bool
    error_message: Optional[str]


# ── Attendance Schemas ─────────────────────────────────────────────────────────
class AttendanceCreate(BaseSchema):
    """Qo'lda davomat kiritish (is_manual=True avtomatik o'rnatiladi)."""
    student_id: uuid.UUID
    lesson_id: uuid.UUID
    status: AttendanceStatus
    check_in_time: Optional[time] = None
    late_minutes: Optional[int] = Field(None, ge=0, le=180)
    note: Optional[str] = None

    @field_validator("late_minutes")
    @classmethod
    def late_only_if_late(cls, v: Optional[int], info) -> Optional[int]:
        status = info.data.get("status")
        if v and v > 0 and status != AttendanceStatus.LATE:
            raise ValueError("late_minutes faqat LATE holat uchun kiritiladi")
        return v


class AttendanceUpdate(BaseSchema):
    """Mavjud davomat yozuvini yangilash."""
    status: Optional[AttendanceStatus] = None
    check_in_time: Optional[time] = None
    late_minutes: Optional[int] = Field(None, ge=0, le=180)
    note: Optional[str] = None


class AttendanceResponse(BaseResponse):
    student_id: uuid.UUID
    lesson_id: uuid.UUID
    status: AttendanceStatus
    check_in_time: Optional[time]
    late_minutes: Optional[int]
    face_log_id: Optional[uuid.UUID]
    is_manual: bool
    manual_by: Optional[uuid.UUID]
    note: Optional[str]


class AttendanceBulkCreate(BaseSchema):
    """
    Butun guruh uchun bir vaqtda davomat kiritish.
    Masalan: O'qituvchi dars boshida barcha o'quvchilarni belgilaydi.
    """
    lesson_id: uuid.UUID
    records: list[AttendanceCreate] = Field(..., min_length=1, max_length=100)


class GroupAttendanceSummary(BaseSchema):
    """Guruh bo'yicha davomat statistikasi."""
    group_id: uuid.UUID
    group_name: str
    total_lessons: int
    total_records: int
    present_pct: float
    absent_pct: float
    late_pct: float


class StudentAttendanceSummary(BaseSchema):
    """Bitta o'quvchining davomat statistikasi."""
    student_id: uuid.UUID
    full_name: str
    present_count: int
    absent_count: int
    late_count: int
    excused_count: int
    attendance_rate: float  # present / total * 100

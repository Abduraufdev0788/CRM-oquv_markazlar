"""
Academic schemas — Course, Room, Group, Enrollment.
"""
import uuid
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Any
from pydantic import field_validator, model_validator, Field

from app.schemas.base import BaseSchema, BaseResponse
from app.schemas.user import UserBriefResponse
from app.schemas.student import StudentBriefResponse
from app.models.academic import GroupStatus, EnrollmentStatus


# ── Course Schemas ─────────────────────────────────────────────────────────────
class CourseCreate(BaseSchema):
    name: str = Field(..., min_length=2, max_length=100, examples=["IELTS Preparation"])
    description: Optional[str] = None
    monthly_fee: Decimal = Field(..., gt=0, examples=[800000])
    duration_months: Optional[int] = Field(None, ge=1, le=60)
    color_hex: Optional[str] = Field(None, examples=["#4F46E5"])

    @field_validator("color_hex")
    @classmethod
    def hex_format(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Rang #RRGGBB formatida bo'lishi kerak (masalan: #4F46E5)")
        return v

    @field_validator("monthly_fee")
    @classmethod
    def fee_precision(cls, v: Decimal) -> Decimal:
        return round(v, 2)


class CourseUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    monthly_fee: Optional[Decimal] = Field(None, gt=0)
    duration_months: Optional[int] = Field(None, ge=1, le=60)
    is_active: Optional[bool] = None
    color_hex: Optional[str] = None

    @field_validator("color_hex")
    @classmethod
    def hex_format(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Rang #RRGGBB formatida bo'lishi kerak")
        return v


class CourseResponse(BaseResponse):
    name: str
    description: Optional[str]
    monthly_fee: Decimal
    duration_months: Optional[int]
    is_active: bool
    color_hex: Optional[str]


class CourseBriefResponse(BaseSchema):
    id: uuid.UUID
    name: str
    monthly_fee: Decimal
    color_hex: Optional[str]


# ── Room Schemas ───────────────────────────────────────────────────────────────
class RoomCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=50, examples=["Xona 1"])
    capacity: int = Field(..., ge=1, le=200, examples=[15])
    floor: Optional[int] = Field(None, ge=0, le=50)
    has_projector: bool = False


class RoomUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    capacity: Optional[int] = Field(None, ge=1, le=200)
    floor: Optional[int] = Field(None, ge=0, le=50)
    has_projector: Optional[bool] = None
    is_active: Optional[bool] = None


class RoomResponse(BaseResponse):
    name: str
    capacity: int
    floor: Optional[int]
    has_projector: bool
    is_active: bool
    current_occupancy: Optional[dict] = None


# ── Group Schedule Item ────────────────────────────────────────────────────────
DAYS_UZ = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?$")


class ScheduleItem(BaseSchema):
    """Dars jadvalining bir elementi."""
    day: str = Field(..., examples=["monday"])
    start: str = Field(..., examples=["09:00"])
    end: str = Field(..., examples=["11:00"])

    @field_validator("day")
    @classmethod
    def day_valid(cls, v: str) -> str:
        if v.lower() not in DAYS_UZ:
            raise ValueError(f"Kun qiymati noto'g'ri. Mumkin bo'lganlar: {DAYS_UZ}")
        return v.lower()

    @field_validator("start", "end")
    @classmethod
    def time_format(cls, v: str) -> str:
        if not TIME_RE.match(v):
            raise ValueError("Vaqt HH:MM formatida bo'lishi kerak (masalan: 09:00)")
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> "ScheduleItem":
        if self.start and self.end and self.end <= self.start:
            raise ValueError("Dars tugash vaqti boshlanish vaqtidan keyin bo'lishi kerak")
        return self


# ── Group Schemas ──────────────────────────────────────────────────────────────
class GroupCreate(BaseSchema):
    name: str = Field(..., min_length=2, max_length=100, examples=["IELTS-2024-A"])
    course_id: uuid.UUID
    room_id: Optional[uuid.UUID] = None
    teacher_id: Optional[uuid.UUID] = None
    start_date: date
    end_date: Optional[date] = None
    max_students: int = Field(default=15, ge=1, le=100)
    teacher_salary_pct: int = Field(default=40, ge=0, le=100)
    schedule: List[ScheduleItem] = Field(..., min_length=1, max_length=7)

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: Optional[date], info) -> Optional[date]:
        start = info.data.get("start_date")
        if v and start and v <= start:
            raise ValueError("Tugash sanasi boshlanish sanasidan keyin bo'lishi kerak")
        return v

    @field_validator("schedule")
    @classmethod
    def no_duplicate_days(cls, v: List[ScheduleItem]) -> List[ScheduleItem]:
        days = [item.day for item in v]
        if len(days) != len(set(days)):
            raise ValueError("Jadvalda bir kun bir marta bo'lishi kerak")
        return v


class GroupUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    course_id: Optional[uuid.UUID] = None
    room_id: Optional[uuid.UUID] = None
    teacher_id: Optional[uuid.UUID] = None
    status: Optional[GroupStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    max_students: Optional[int] = Field(None, ge=1, le=100)
    teacher_salary_pct: Optional[int] = Field(None, ge=0, le=100)
    schedule: Optional[List[ScheduleItem]] = None


class GroupResponse(BaseResponse):
    name: str
    course_id: uuid.UUID
    room_id: Optional[uuid.UUID]
    teacher_id: Optional[uuid.UUID]
    status: GroupStatus
    start_date: date
    end_date: Optional[date]
    max_students: int
    teacher_salary_pct: int
    schedule: List[dict]
    # Nested
    teacher: Optional[UserBriefResponse] = None
    course: Optional[CourseBriefResponse] = None
    room: Optional[RoomResponse] = None
    enrolled_count: Optional[int] = None  # DB query dan qo'shiladi


class GroupBriefResponse(BaseSchema):
    id: uuid.UUID
    name: str
    status: GroupStatus
    start_date: date
    end_date: Optional[date] = None
    max_students: int
    teacher_salary_pct: int
    schedule: List[dict] = Field(default_factory=list)
    room_id: Optional[uuid.UUID] = None
    room: Optional[RoomResponse] = None
    course: Optional[CourseBriefResponse] = None


# ── Material Schemas ───────────────────────────────────────────────────────────
class MaterialCreate(BaseSchema):
    group_id: uuid.UUID
    title: str
    description: Optional[str] = None
    file_url: str
    file_type: Optional[str] = None

class MaterialResponse(BaseResponse):
    group_id: uuid.UUID
    title: str
    description: Optional[str] = None
    file_url: str
    file_type: Optional[str] = None
    uploaded_by: uuid.UUID
    uploader: Optional[UserBriefResponse] = None
    group: Optional[GroupBriefResponse] = None


# ── Test Schemas ───────────────────────────────────────────────────────────────
class QuestionSchema(BaseSchema):
    text: str
    type: str = "choice" # e.g. "choice", "text"
    options: Optional[List[str]] = None
    correct_answer: Optional[int] = None # index of correct option if choice

class TestCreate(BaseSchema):
    group_id: uuid.UUID
    title: str
    description: Optional[str] = None
    questions: List[QuestionSchema]
    max_score: int = 100
    is_active: bool = True
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    max_attempts: int = 1

class TestUpdate(BaseSchema):
    title: Optional[str] = None
    description: Optional[str] = None
    questions: Optional[List[QuestionSchema]] = None
    max_score: Optional[int] = None
    is_active: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    max_attempts: Optional[int] = None

class TestResponse(BaseResponse):
    group_id: uuid.UUID
    teacher_id: uuid.UUID
    title: str
    description: Optional[str] = None
    questions: List[QuestionSchema] = Field(default_factory=list)
    max_score: int
    is_active: bool
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    max_attempts: int
    attempts_used: Optional[int] = None
    teacher: Optional[UserBriefResponse] = None
    group: Optional[GroupBriefResponse] = None

class TestSubmit(BaseSchema):
    answers: dict[str, int] # e.g., {"0": 1, "1": 3} where key is question index, value is selected option index

class TestResultCreate(BaseSchema):
    test_id: uuid.UUID
    student_id: uuid.UUID
    score: int
    answers: dict

class TestResultResponse(BaseResponse):
    test_id: uuid.UUID
    student_id: uuid.UUID
    score: int
    answers: dict
    student: Optional[StudentBriefResponse] = None


# ── Enrollment Schemas ─────────────────────────────────────────────────────────
class EnrollmentCreate(BaseSchema):
    student_id: uuid.UUID
    group_id: uuid.UUID
    discount_pct: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    notes: Optional[str] = None

    @field_validator("discount_pct")
    @classmethod
    def discount_precision(cls, v: Decimal) -> Decimal:
        return round(v, 2)


class EnrollmentUpdate(BaseSchema):
    status: Optional[EnrollmentStatus] = None
    discount_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    notes: Optional[str] = None


class EnrollmentResponse(BaseResponse):
    student_id: uuid.UUID
    group_id: uuid.UUID
    status: EnrollmentStatus
    enrolled_at: date
    dropped_at: Optional[date]
    discount_pct: Decimal
    notes: Optional[str]
    # Nested uchun
    group: Optional[GroupBriefResponse] = None
    student: Optional[StudentBriefResponse] = None

"""
Lesson, Homework, Grade schemas.
"""
import uuid
from datetime import date, time
from decimal import Decimal
from typing import Optional, List
from pydantic import field_validator, model_validator, Field

from app.schemas.base import BaseSchema, BaseResponse
from app.models.lesson import GradeType


# ── Lesson Schemas ─────────────────────────────────────────────────────────────
class LessonCreate(BaseSchema):
    group_id: uuid.UUID
    title: Optional[str] = Field(None, max_length=200, examples=["Unit 5: Reading Comprehension"])
    lesson_date: date
    start_time: time = Field(..., examples=["09:00"])
    end_time: time = Field(..., examples=["11:00"])
    topic: Optional[str] = Field(None, max_length=500)

    @field_validator("lesson_date")
    @classmethod
    def not_too_old(cls, v: date) -> date:
        from datetime import timedelta
        if v < date.today() - timedelta(days=30):
            raise ValueError("Dars sanasi 30 kundan eski bo'lishi mumkin emas")
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> "LessonCreate":
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("Dars tugash vaqti boshlanish vaqtidan keyin bo'lishi kerak")
        return self


class LessonUpdate(BaseSchema):
    title: Optional[str] = Field(None, max_length=200)
    topic: Optional[str] = None
    is_cancelled: Optional[bool] = None
    cancel_reason: Optional[str] = None


class LessonResponse(BaseResponse):
    group_id: uuid.UUID
    title: Optional[str]
    lesson_date: date
    start_time: time
    end_time: time
    topic: Optional[str]
    is_cancelled: bool
    cancel_reason: Optional[str]


class LessonBriefResponse(BaseSchema):
    id: uuid.UUID
    lesson_date: date
    start_time: time
    end_time: time
    is_cancelled: bool


# ── Homework Schemas ───────────────────────────────────────────────────────────
class HomeworkCreate(BaseSchema):
    lesson_id: uuid.UUID
    title: str = Field(..., min_length=2, max_length=200, examples=["Reading: Pages 45-50"])
    description: Optional[str] = None
    due_date: Optional[date] = None
    max_score: Decimal = Field(default=Decimal("100.00"), gt=0, le=1000)
    file_url: Optional[str] = Field(None, max_length=255)

    @field_validator("due_date")
    @classmethod
    def due_future(cls, v: Optional[date]) -> Optional[date]:
        if v and v < date.today():
            raise ValueError("Topshirish muddati o'tgan sana bo'lishi mumkin emas")
        return v


class HomeworkUpdate(BaseSchema):
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    due_date: Optional[date] = None
    max_score: Optional[Decimal] = Field(None, gt=0, le=1000)
    file_url: Optional[str] = None


class HomeworkResponse(BaseResponse):
    lesson_id: uuid.UUID
    title: str
    description: Optional[str]
    due_date: Optional[date]
    max_score: Decimal
    file_url: Optional[str]


# ── Grade Schemas ──────────────────────────────────────────────────────────────
class GradeCreate(BaseSchema):
    student_id: uuid.UUID
    grade_type: GradeType
    score: Decimal = Field(..., ge=0)
    max_score: Decimal = Field(default=Decimal("100.00"), gt=0, le=1000)
    lesson_id: Optional[uuid.UUID] = None
    homework_id: Optional[uuid.UUID] = None
    comment: Optional[str] = None

    @model_validator(mode="after")
    def score_not_exceed_max(self) -> "GradeCreate":
        if self.score > self.max_score:
            raise ValueError(f"Ball ({self.score}) maksimal balldan ({self.max_score}) oshmasligi kerak")
        return self

    @model_validator(mode="after")
    def source_required(self) -> "GradeCreate":
        """Grade type ga qarab lesson_id yoki homework_id bo'lishi kerak."""
        if self.grade_type == GradeType.HOMEWORK and not self.homework_id:
            raise ValueError("Uy vazifasi bahosi uchun homework_id talab qilinadi")
        if self.grade_type in (GradeType.LESSON, GradeType.EXAM) and not self.lesson_id:
            raise ValueError("Dars/imtihon bahosi uchun lesson_id talab qilinadi")
        return self


class GradeUpdate(BaseSchema):
    score: Optional[Decimal] = Field(None, ge=0)
    comment: Optional[str] = None


class GradeResponse(BaseResponse):
    student_id: uuid.UUID
    lesson_id: Optional[uuid.UUID]
    homework_id: Optional[uuid.UUID]
    grade_type: GradeType
    score: Decimal
    max_score: Decimal
    comment: Optional[str]
    graded_by: Optional[uuid.UUID]

    @property
    def percentage(self) -> float:
        if self.max_score == 0:
            return 0.0
        return round(float(self.score / self.max_score * 100), 1)


class StudentGradeSummary(BaseSchema):
    """O'quvchining ma'lum guruh bo'yicha o'rtacha bahosi."""
    student_id: uuid.UUID
    full_name: str
    average_score: Optional[float]
    total_grades: int
    homework_avg: Optional[float]
    lesson_avg: Optional[float]

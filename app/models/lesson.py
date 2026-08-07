import uuid
import enum
from datetime import date, time
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import (
    String, Boolean, Date, Time, SmallInteger,
    Numeric, Text, Enum as SAEnum, ForeignKey, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.academic import Group
    from app.models.student import Student
    from app.models.user import User
    from app.models.iot import Attendance


class Lesson(BaseModel):
    __tablename__ = "lessons"

    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    topic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    group: Mapped["Group"] = relationship(back_populates="lessons")
    homeworks: Mapped[List["Homework"]] = relationship(back_populates="lesson")
    grades: Mapped[List["Grade"]] = relationship(back_populates="lesson")
    attendances: Mapped[List["Attendance"]] = relationship(back_populates="lesson")


class Homework(BaseModel):
    __tablename__ = "homeworks"

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    max_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("100.00"))
    file_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    lesson: Mapped["Lesson"] = relationship(back_populates="homeworks")
    grades: Mapped[List["Grade"]] = relationship(back_populates="homework")


class GradeType(str, enum.Enum):
    HOMEWORK = "homework"
    LESSON = "lesson"
    EXAM = "exam"


class Grade(BaseModel):
    __tablename__ = "grades"

    __table_args__ = (
        CheckConstraint("score <= max_score", name="ck_grades_score_valid"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True
    )
    lesson_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=True, index=True
    )
    homework_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("homeworks.id"), nullable=True
    )
    grade_type: Mapped[GradeType] = mapped_column(
        SAEnum(GradeType, name="gradetype"), nullable=False
    )
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("100.00"))
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    graded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    student: Mapped["Student"] = relationship(back_populates="grades")
    lesson: Mapped[Optional["Lesson"]] = relationship(back_populates="grades")
    homework: Mapped[Optional["Homework"]] = relationship(back_populates="grades")

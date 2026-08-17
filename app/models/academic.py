import uuid
import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import (
    String, Boolean, Date, DateTime, SmallInteger, Numeric,
    Enum as SAEnum, ForeignKey, UniqueConstraint, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.student import Student
    from app.models.lesson import Lesson


class GroupStatus(str, enum.Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    ARCHIVED = "archived"


class EnrollmentStatus(str, enum.Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    DROPPED = "dropped"


class Course(BaseModel):
    __tablename__ = "courses"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    monthly_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    duration_months: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    color_hex: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # "#FF5733"

    # Relationships
    groups: Mapped[List["Group"]] = relationship(back_populates="course")


class Room(BaseModel):
    __tablename__ = "rooms"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    capacity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    floor: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    has_projector: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    groups: Mapped[List["Group"]] = relationship(back_populates="room")


class Group(BaseModel):
    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True
    )
    room_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=True
    )
    teacher_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[GroupStatus] = mapped_column(
        SAEnum(GroupStatus, name="groupstatus"), nullable=False, default=GroupStatus.PLANNED, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    max_students: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=15)
    teacher_salary_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("40.00"))
    # schedule: [{"day": "monday", "start": "09:00", "end": "11:00"}, ...]
    schedule: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="groups")
    room: Mapped[Optional["Room"]] = relationship(back_populates="groups")
    teacher: Mapped[Optional["User"]] = relationship(back_populates="groups")
    enrollments: Mapped[List["Enrollment"]] = relationship(back_populates="group")
    lessons: Mapped[List["Lesson"]] = relationship(back_populates="group")
    materials: Mapped[List["Material"]] = relationship(back_populates="group")
    tests: Mapped[List["Test"]] = relationship(back_populates="group")


class Material(BaseModel):
    __tablename__ = "materials"

    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_url: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    group: Mapped["Group"] = relationship(back_populates="materials")
    uploader: Mapped["User"] = relationship()


class Test(BaseModel):
    __tablename__ = "tests"

    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    questions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    max_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    # Relationships
    group: Mapped["Group"] = relationship(back_populates="tests")
    teacher: Mapped["User"] = relationship()
    results: Mapped[List["TestResult"]] = relationship(back_populates="test", cascade="all, delete-orphan")


class TestResult(BaseModel):
    __tablename__ = "test_results"

    test_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tests.id"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True
    )
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Relationships
    test: Mapped["Test"] = relationship(back_populates="results")
    student: Mapped["Student"] = relationship()


class Enrollment(BaseModel):
    __tablename__ = "enrollments"

    __table_args__ = (
        UniqueConstraint("student_id", "group_id", name="uq_enrollment_student_group"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        SAEnum(EnrollmentStatus, name="enrollmentstatus"),
        nullable=False, default=EnrollmentStatus.ACTIVE, index=True
    )
    enrolled_at: Mapped[date] = mapped_column(Date, nullable=False)
    dropped_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    student: Mapped["Student"] = relationship(back_populates="enrollments")
    group: Mapped["Group"] = relationship(back_populates="enrollments")
    payments: Mapped[List["Payment"]] = relationship(back_populates="enrollment")

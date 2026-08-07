import uuid
import enum
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, Date, Numeric, Enum as SAEnum, ForeignKey, CheckConstraint, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.academic import Enrollment
    from app.models.finance import Payment
    from app.models.iot import FaceLog
    from app.models.lesson import Grade
    from app.models.system import Notification


class StudentStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    GRADUATED = "graduated"
    EXPELLED = "expelled"


class Parent(BaseModel):
    __tablename__ = "parents"

    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    is_bot_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    students: Mapped[List["Student"]] = relationship(back_populates="parent")


class Student(BaseModel):
    __tablename__ = "students"

    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_students_balance_positive"),
    )

    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)
    birth_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("parents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[StudentStatus] = mapped_column(
        SAEnum(StudentStatus, name="studentstatus"), nullable=False, default=StudentStatus.ACTIVE, index=True
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    face_data_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    parent: Mapped[Optional["Parent"]] = relationship(back_populates="students")
    enrollments: Mapped[List["Enrollment"]] = relationship(back_populates="student")
    payments: Mapped[List["Payment"]] = relationship(back_populates="student")
    grades: Mapped[List["Grade"]] = relationship(back_populates="student")
    face_logs: Mapped[List["FaceLog"]] = relationship(back_populates="student")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="student")

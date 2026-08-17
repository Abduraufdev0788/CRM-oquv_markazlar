import uuid
import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import (
    String, Date, SmallInteger, Numeric, Text,
    Enum as SAEnum, ForeignKey, DateTime, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.student import Student
    from app.models.academic import Enrollment
    from app.models.user import User


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    CLICK = "click"
    PAYME = "payme"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class ExpenseCategory(str, enum.Enum):
    RENT = "rent"
    SALARY = "salary"
    UTILITY = "utility"
    EQUIPMENT = "equipment"
    MARKETING = "marketing"
    OTHER = "other"


class SalaryStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"


class Payment(BaseModel):
    __tablename__ = "payments"

    student_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True
    )
    enrollment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        SAEnum(PaymentMethod, name="paymentmethod"), nullable=False
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="paymentstatus"),
        nullable=False, default=PaymentStatus.CONFIRMED, index=True
    )
    period_month: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1-12
    period_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)   # 2024
    transaction_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    receipt_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    student: Mapped["Student"] = relationship(back_populates="payments")
    enrollment: Mapped[Optional["Enrollment"]] = relationship(back_populates="payments")

    @property
    def group_name(self) -> Optional[str]:
        if self.enrollment and self.enrollment.group:
            return self.enrollment.group.name
        return None


class Expense(BaseModel):
    __tablename__ = "expenses"

    category: Mapped[ExpenseCategory] = mapped_column(
        SAEnum(ExpenseCategory, name="expensecategory"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expense_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    receipt_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


class Salary(BaseModel):
    __tablename__ = "salaries"

    __table_args__ = (
        UniqueConstraint("user_id", "period_month", "period_year", name="uq_salary_user_period"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    period_month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    period_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    bonus_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    penalty_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    status: Mapped[SalaryStatus] = mapped_column(
        SAEnum(SalaryStatus, name="salarystatus"),
        nullable=False, default=SalaryStatus.PENDING, index=True
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Computed property
    @property
    def total_amount(self) -> Decimal:
        return self.base_amount + self.bonus_amount - self.penalty_amount

    # Relationships
    user: Mapped["User"] = relationship(back_populates="salaries", foreign_keys=[user_id])

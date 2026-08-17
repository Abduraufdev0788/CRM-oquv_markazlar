"""
Finance schemas — Payment, Expense, Salary.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import field_validator, model_validator, Field

from app.schemas.base import BaseSchema, BaseResponse
from app.models.finance import PaymentMethod, PaymentStatus, ExpenseCategory, SalaryStatus


# ── Payment Schemas ────────────────────────────────────────────────────────────
class PaymentCreate(BaseSchema):
    student_id: uuid.UUID
    enrollment_id: Optional[uuid.UUID] = None
    amount: Decimal = Field(..., gt=0, examples=[800000])
    method: PaymentMethod
    period_month: int = Field(..., ge=1, le=12, examples=[8])
    period_year: int = Field(..., ge=2020, le=2100, examples=[2024])
    transaction_id: Optional[str] = Field(
        None, max_length=100,
        description="Click/Payme tranzaksiya ID (online to'lovlar uchun)"
    )
    comment: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_precision(cls, v: Decimal) -> Decimal:
        return round(v, 2)


class PaymentUpdate(BaseSchema):
    """Faqat Admin to'lov holatini o'zgartira oladi."""
    status: Optional[PaymentStatus] = None
    comment: Optional[str] = None


class PaymentResponse(BaseResponse):
    student_id: uuid.UUID
    enrollment_id: Optional[uuid.UUID]
    amount: Decimal
    method: PaymentMethod
    status: PaymentStatus
    period_month: int
    period_year: int
    transaction_id: Optional[str]
    comment: Optional[str]
    created_by: Optional[uuid.UUID]


from app.schemas.student import StudentBriefResponse

class PaymentBriefResponse(BaseSchema):
    id: uuid.UUID
    amount: Decimal
    method: PaymentMethod
    status: PaymentStatus
    period_month: int
    period_year: int
    created_at: datetime
    student_id: uuid.UUID
    enrollment_id: Optional[uuid.UUID] = None
    group_name: Optional[str] = None
    student: Optional[StudentBriefResponse] = None


class MonthlyPaymentSummary(BaseSchema):
    """Oylik to'lov statistikasi."""
    period_month: int
    period_year: int
    total_collected: Decimal
    total_pending: Decimal
    payment_count: int
    by_method: dict  # {"cash": 500000, "card": 300000}


# ── Expense Schemas ────────────────────────────────────────────────────────────
class ExpenseCreate(BaseSchema):
    category: ExpenseCategory
    amount: Decimal = Field(..., gt=0, examples=[2000000])
    description: str = Field(..., min_length=3, max_length=500, examples=["Mart oyi ijarasi"])
    expense_date: date = Field(default_factory=date.today)
    receipt_url: Optional[str] = Field(None, max_length=255)

    @field_validator("expense_date")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Xarajat sanasi kelajakda bo'lishi mumkin emas")
        return v

    @field_validator("amount")
    @classmethod
    def amount_precision(cls, v: Decimal) -> Decimal:
        return round(v, 2)


class ExpenseUpdate(BaseSchema):
    category: Optional[ExpenseCategory] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    description: Optional[str] = Field(None, min_length=3, max_length=500)
    expense_date: Optional[date] = None
    receipt_url: Optional[str] = None


class ExpenseResponse(BaseResponse):
    category: ExpenseCategory
    amount: Decimal
    description: str
    expense_date: date
    receipt_url: Optional[str]
    created_by: Optional[uuid.UUID]


class ExpenseSummary(BaseSchema):
    """Xarajat kategoriya bo'yicha umumlashtirish."""
    category: ExpenseCategory
    total: Decimal
    count: int


# ── Salary Schemas ─────────────────────────────────────────────────────────────
class SalaryCreate(BaseSchema):
    user_id: uuid.UUID
    period_month: int = Field(..., ge=1, le=12)
    period_year: int = Field(..., ge=2020, le=2100)
    base_amount: Decimal = Field(..., gt=0, examples=[3000000])
    bonus_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    penalty_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    comment: Optional[str] = None

    @model_validator(mode="after")
    def total_positive(self) -> "SalaryCreate":
        total = self.base_amount + self.bonus_amount - self.penalty_amount
        if total <= 0:
            raise ValueError("Jami maosh (base + bonus - jarima) musbat bo'lishi kerak")
        return self


class SalaryUpdate(BaseSchema):
    bonus_amount: Optional[Decimal] = Field(None, ge=0)
    penalty_amount: Optional[Decimal] = Field(None, ge=0)
    comment: Optional[str] = None


class SalaryPayRequest(BaseSchema):
    """Maosh to'lash amali uchun so'rov."""
    comment: Optional[str] = None


from app.schemas.user import UserBriefResponse

class SalaryResponse(BaseResponse):
    user_id: uuid.UUID
    period_month: int
    period_year: int
    base_amount: Decimal
    bonus_amount: Decimal
    penalty_amount: Decimal
    status: SalaryStatus
    paid_at: Optional[datetime]
    paid_by: Optional[uuid.UUID]
    comment: Optional[str]
    user: Optional[UserBriefResponse] = None

    @property
    def total_amount(self) -> Decimal:
        return self.base_amount + self.bonus_amount - self.penalty_amount

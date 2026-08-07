"""
Finance API — Payment, Expense, Salary — /api/v1/finance/
"""
import uuid
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timezone

from app.database import get_db
from app.models.user import User, UserRole
from app.models.finance import Payment, PaymentStatus, Expense, Salary, SalaryStatus
from app.models.student import Student
from app.core.dependencies import require_roles
from app.schemas import (
    PaymentCreate, PaymentUpdate, PaymentResponse, PaymentBriefResponse,
    ExpenseCreate, ExpenseUpdate, ExpenseResponse,
    SalaryCreate, SalaryUpdate, SalaryPayRequest, SalaryResponse,
    PaginatedResponse, MessageResponse,
)

router = APIRouter(prefix="/finance", tags=["Finance (Moliya)"])

AnyStaff = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
AdminOnly = Depends(require_roles(UserRole.ADMIN))


# ═══════════════════════════════════════════════════════════════════════════════
# PAYMENTS
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/payments/", response_model=PaginatedResponse[PaymentBriefResponse], summary="To'lovlar ro'yxati")
async def list_payments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    student_id: Optional[uuid.UUID] = None,
    period_month: Optional[int] = Query(None, ge=1, le=12),
    period_year: Optional[int] = Query(None, ge=2020),
    pay_status: Optional[PaymentStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(Payment)
    if student_id:
        query = query.where(Payment.student_id == student_id)
    if period_month:
        query = query.where(Payment.period_month == period_month)
    if period_year:
        query = query.where(Payment.period_year == period_year)
    if pay_status:
        query = query.where(Payment.status == pay_status)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    payments = (await db.execute(query.offset(skip).limit(limit).order_by(Payment.created_at.desc()))).scalars().all()
    return PaginatedResponse.create(data=payments, total=total, skip=skip, limit=limit)


@router.post("/payments/", response_model=PaymentResponse, status_code=201, summary="To'lov qabul qilish")
async def create_payment(
    data: PaymentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    # O'quvchi mavjudligini tekshirish
    student = (await db.execute(select(Student).where(Student.id == data.student_id))).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")

    payment = Payment(
        **data.model_dump(),
        created_by=current_user.id,
        status=PaymentStatus.CONFIRMED,
    )
    db.add(payment)

    # O'quvchi balansini yangilash
    student.balance += data.amount

    await db.flush()
    await db.refresh(payment)
    return payment


@router.put("/payments/{payment_id}", response_model=PaymentResponse, summary="To'lov holatini o'zgartirish")
async def update_payment(
    payment_id: uuid.UUID,
    data: PaymentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    payment = (await db.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="To'lov topilmadi")

    # CANCELLED bo'lganda balansdan olib tashlash
    if data.status == PaymentStatus.CANCELLED and payment.status == PaymentStatus.CONFIRMED:
        student = (await db.execute(select(Student).where(Student.id == payment.student_id))).scalar_one()
        student.balance = max(0, student.balance - payment.amount)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(payment, key, value)

    await db.flush()
    await db.refresh(payment)
    return payment


# ═══════════════════════════════════════════════════════════════════════════════
# EXPENSES
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/expenses/", response_model=PaginatedResponse[ExpenseResponse], summary="Xarajatlar ro'yxati")
async def list_expenses(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(Expense).order_by(Expense.expense_date.desc())
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    expenses = (await db.execute(query.offset(skip).limit(limit))).scalars().all()
    return PaginatedResponse.create(data=expenses, total=total, skip=skip, limit=limit)


@router.post("/expenses/", response_model=ExpenseResponse, status_code=201, summary="Xarajat qo'shish")
async def create_expense(
    data: ExpenseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    expense = Expense(**data.model_dump(), created_by=current_user.id)
    db.add(expense)
    await db.flush()
    await db.refresh(expense)
    return expense


@router.delete("/expenses/{expense_id}", response_model=MessageResponse, summary="Xarajatni o'chirish")
async def delete_expense(
    expense_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    expense = (await db.execute(select(Expense).where(Expense.id == expense_id))).scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Xarajat topilmadi")
    await db.delete(expense)
    return MessageResponse(detail="Xarajat o'chirildi")


# ═══════════════════════════════════════════════════════════════════════════════
# SALARIES
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/salaries/", response_model=PaginatedResponse[SalaryResponse], summary="Maoshlar ro'yxati")
async def list_salaries(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    user_id: Optional[uuid.UUID] = None,
    period_month: Optional[int] = Query(None, ge=1, le=12),
    period_year: Optional[int] = Query(None, ge=2020),
    sal_status: Optional[SalaryStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    # O'qituvchi faqat o'z maoshini ko'radi
    if current_user.role == UserRole.TEACHER:
        user_id = current_user.id

    query = select(Salary)
    if user_id:
        query = query.where(Salary.user_id == user_id)
    if period_month:
        query = query.where(Salary.period_month == period_month)
    if period_year:
        query = query.where(Salary.period_year == period_year)
    if sal_status:
        query = query.where(Salary.status == sal_status)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    salaries = (await db.execute(query.offset(skip).limit(limit).order_by(Salary.created_at.desc()))).scalars().all()
    return PaginatedResponse.create(data=salaries, total=total, skip=skip, limit=limit)


@router.post("/salaries/", response_model=SalaryResponse, status_code=201, summary="Maosh hisoblash")
async def create_salary(
    data: SalaryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    # Takroriy hisoblashni tekshirish
    existing = (await db.execute(
        select(Salary).where(
            and_(
                Salary.user_id == data.user_id,
                Salary.period_month == data.period_month,
                Salary.period_year == data.period_year,
            )
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"{data.period_month}/{data.period_year} uchun maosh allaqachon hisoblangan",
        )

    salary = Salary(**data.model_dump())
    db.add(salary)
    await db.flush()
    await db.refresh(salary)
    return salary


@router.post("/salaries/{salary_id}/pay", response_model=SalaryResponse, summary="Maosh to'lash")
async def pay_salary(
    salary_id: uuid.UUID,
    data: SalaryPayRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    salary = (await db.execute(select(Salary).where(Salary.id == salary_id))).scalar_one_or_none()
    if not salary:
        raise HTTPException(status_code=404, detail="Maosh topilmadi")
    if salary.status == SalaryStatus.PAID:
        raise HTTPException(status_code=400, detail="Bu maosh allaqachon to'langan")

    salary.status = SalaryStatus.PAID
    salary.paid_at = datetime.now(timezone.utc)
    salary.paid_by = current_user.id
    if data.comment:
        salary.comment = data.comment

    await db.flush()
    await db.refresh(salary)
    return salary

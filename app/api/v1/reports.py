"""
Reports API — /api/v1/reports/
Moliya va davomat hisobotlari.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models.user import User, UserRole
from app.models.finance import Payment, Expense, PaymentStatus, ExpenseCategory
from app.models.iot import Attendance, AttendanceStatus
from app.models.lesson import Lesson
from app.models.academic import Group, Enrollment, EnrollmentStatus
from app.core.dependencies import require_roles

router = APIRouter(prefix="/reports", tags=["Reports (Hisobotlar)"])

ManagerOrAdmin = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
AdminOnly = Depends(require_roles(UserRole.ADMIN))


@router.get("/finance", summary="Oylik moliyaviy hisobot")
async def finance_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
):
    """
    Berilgan oy bo'yicha:
    - Jami tushum (to'lovlar)
    - Jami xarajat
    - Sof foyda
    - To'lov usuli bo'yicha taqsimot
    """
    # Tushum
    income_result = await db.execute(
        select(
            Payment.method,
            func.sum(Payment.amount).label("total"),
            func.count(Payment.id).label("count"),
        )
        .where(
            and_(
                Payment.period_month == month,
                Payment.period_year == year,
                Payment.status == PaymentStatus.CONFIRMED,
            )
        )
        .group_by(Payment.method)
    )
    income_by_method = {row.method: {"total": float(row.total), "count": row.count}
                        for row in income_result}
    total_income = sum(v["total"] for v in income_by_method.values())

    # Xarajat
    expense_result = await db.execute(
        select(
            Expense.category,
            func.sum(Expense.amount).label("total"),
        )
        .where(
            and_(
                func.extract("month", Expense.expense_date) == month,
                func.extract("year", Expense.expense_date) == year,
            )
        )
        .group_by(Expense.category)
    )
    expense_by_category = {row.category: float(row.total) for row in expense_result}
    total_expense = sum(expense_by_category.values())

    return {
        "period": f"{year}-{month:02d}",
        "income": {
            "total": total_income,
            "by_method": income_by_method,
        },
        "expense": {
            "total": total_expense,
            "by_category": expense_by_category,
        },
        "net_profit": round(total_income - total_expense, 2),
    }


@router.get("/attendance", summary="Guruh davomat hisoboti")
async def attendance_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
    group_id: uuid.UUID = Query(...),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    """
    Guruh bo'yicha har bir o'quvchining davomat ko'rsatkichi.
    """
    # Guruh o'quvchilari
    enrollments = (await db.execute(
        select(Enrollment).where(
            and_(Enrollment.group_id == group_id, Enrollment.status == EnrollmentStatus.ACTIVE)
        )
    )).scalars().all()

    # Guruh darslari
    lesson_query = select(Lesson).where(Lesson.group_id == group_id)
    if date_from:
        lesson_query = lesson_query.where(Lesson.lesson_date >= date_from)
    if date_to:
        lesson_query = lesson_query.where(Lesson.lesson_date <= date_to)
    lessons = (await db.execute(lesson_query)).scalars().all()
    lesson_ids = [l.id for l in lessons]
    total_lessons = len(lesson_ids)

    results = []
    for enrollment in enrollments:
        if not lesson_ids:
            stats = {"present": 0, "absent": 0, "late": 0, "excused": 0, "rate": 0.0}
        else:
            att_result = await db.execute(
                select(Attendance.status, func.count(Attendance.id).label("cnt"))
                .where(
                    and_(
                        Attendance.student_id == enrollment.student_id,
                        Attendance.lesson_id.in_(lesson_ids),
                    )
                )
                .group_by(Attendance.status)
            )
            counts = {row.status: row.cnt for row in att_result}
            present = counts.get(AttendanceStatus.PRESENT, 0)
            stats = {
                "present": present,
                "absent": counts.get(AttendanceStatus.ABSENT, 0),
                "late": counts.get(AttendanceStatus.LATE, 0),
                "excused": counts.get(AttendanceStatus.EXCUSED, 0),
                "rate": round(present / total_lessons * 100, 1) if total_lessons else 0.0,
            }

        results.append({
            "student_id": str(enrollment.student_id),
            "enrollment_id": str(enrollment.id),
            **stats,
        })

    return {
        "group_id": str(group_id),
        "total_lessons": total_lessons,
        "date_from": str(date_from) if date_from else None,
        "date_to": str(date_to) if date_to else None,
        "students": results,
    }


@router.get("/debtors", summary="Qarzdor o'quvchilar ro'yxati")
async def debtors_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    group_id: Optional[uuid.UUID] = Query(None, description="Filtrlash uchun guruh ID si"),
):
    """
    Berilgan oy uchun to'lov qilmagan aktiv o'quvchilar.
    """
    from app.models.student import Student
    from sqlalchemy.orm import selectinload

    # 1. Shu oy uchun qilingan barcha to'lovlarni guruhlab olamiz
    payments_result = await db.execute(
        select(Payment.student_id, func.sum(Payment.amount).label("total_paid"))
        .where(
            and_(
                Payment.period_month == month,
                Payment.period_year == year,
                Payment.status == PaymentStatus.CONFIRMED,
            )
        )
        .group_by(Payment.student_id)
    )
    paid_amounts = {row.student_id: row.total_paid for row in payments_result}

    # 2. Barcha aktiv o'quvchilarni kurslari bilan tortib olamiz
    student_query = (
        select(Student)
        .options(
            selectinload(Student.enrollments).selectinload(Enrollment.group).selectinload(Group.course)
        )
    )

    if group_id:
        student_query = student_query.where(
            Student.id.in_(
                select(Enrollment.student_id).where(
                    and_(
                        Enrollment.status == EnrollmentStatus.ACTIVE,
                        Enrollment.group_id == group_id
                    )
                )
            )
        )
    else:
        student_query = student_query.where(
            Student.id.in_(
                select(Enrollment.student_id).where(Enrollment.status == EnrollmentStatus.ACTIVE)
            )
        )

    students = (await db.execute(student_query)).scalars().all()

    debtors_list = []
    for s in students:
        total_required = Decimal("0.00")
        groups_list = []
        
        for enr in s.enrollments:
            if enr.status == EnrollmentStatus.ACTIVE and enr.group and enr.group.course:
                course_fee = enr.group.course.monthly_fee
                discount = enr.discount_pct
                required = course_fee * (Decimal("1") - discount / Decimal("100"))
                total_required += required
                groups_list.append(enr.group.name)
                
        total_paid = paid_amounts.get(s.id, Decimal("0.00"))
        debt = total_required - total_paid
        
        if debt > 0:
            debtors_list.append({
                "id": str(s.id),
                "full_name": s.full_name,
                "phone": s.phone,
                "balance": float(debt),  # Hozirgi oy uchun aniq qarz
                "groups": groups_list
            })

    # Qarzi eng ko'plarni birinchi chiqarish (Saralash)
    debtors_list.sort(key=lambda x: x["balance"], reverse=True)

    return {
        "period": f"{year}-{month:02d}",
        "count": len(debtors_list),
        "debtors": debtors_list,
    }

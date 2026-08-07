"""
Report Service — Hisobot va statistika biznes logikasi.
"""
import logging
from decimal import Decimal
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.finance import Payment, Expense, PaymentStatus
from app.models.iot import Attendance, AttendanceStatus
from app.models.lesson import Lesson
from app.models.academic import Group, Enrollment, EnrollmentStatus
from app.models.student import Student

logger = logging.getLogger(__name__)


async def get_dashboard_stats(db: AsyncSession) -> dict:
    """
    Bosh sahifa uchun umumiy statistika:
    - Jami aktiv o'quvchilar
    - Bu oy tushumi
    - Bu oy xarajati
    - Bugungi davomat foizi
    """
    from datetime import datetime, timezone
    today = date.today()
    month = today.month
    year = today.year

    # Aktiv o'quvchilar
    from app.models.student import StudentStatus
    student_count = (await db.execute(
        select(func.count(Student.id)).where(Student.status == StudentStatus.ACTIVE)
    )).scalar_one()

    # Bu oy tushumi
    monthly_income = (await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            and_(
                Payment.period_month == month,
                Payment.period_year == year,
                Payment.status == PaymentStatus.CONFIRMED,
            )
        )
    )).scalar_one()

    # Bu oy xarajati
    monthly_expense = (await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            and_(
                func.extract("month", Expense.expense_date) == month,
                func.extract("year", Expense.expense_date) == year,
            )
        )
    )).scalar_one()

    # Bugungi davomat foizi
    today_lessons = (await db.execute(
        select(Lesson.id).where(Lesson.lesson_date == today)
    )).scalars().all()

    today_att_rate = 0.0
    if today_lessons:
        total_att = (await db.execute(
            select(func.count(Attendance.id)).where(
                Attendance.lesson_id.in_(today_lessons)
            )
        )).scalar_one()

        present_att = (await db.execute(
            select(func.count(Attendance.id)).where(
                and_(
                    Attendance.lesson_id.in_(today_lessons),
                    Attendance.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE]),
                )
            )
        )).scalar_one()

        today_att_rate = round(present_att / total_att * 100, 1) if total_att > 0 else 0.0

    return {
        "active_students": student_count,
        "monthly_income": float(monthly_income),
        "monthly_expense": float(monthly_expense),
        "net_profit": float(Decimal(str(monthly_income)) - Decimal(str(monthly_expense))),
        "today_attendance_rate": today_att_rate,
        "today_lessons_count": len(today_lessons),
    }

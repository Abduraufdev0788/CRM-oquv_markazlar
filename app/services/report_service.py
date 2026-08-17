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
from app.models.lead import Lead, LeadStatus

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
                func.extract("month", Payment.created_at) == month,
                func.extract("year", Payment.created_at) == year,
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

    # ── Yangi Pro Statistikalar ──
    from dateutil.relativedelta import relativedelta
    from app.models.academic import GroupStatus
    from app.models.user import User, UserRole

    # 1. Daromad Dinamikasi va Yangi O'quvchilar O'sishi (Oxirgi 6 oy)
    income_trend = []
    new_students_trend = []
    months_uz = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
    for i in range(5, -1, -1):
        m_date = today - relativedelta(months=i)
        
        # Daromad
        inc = (await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                and_(
                    func.extract("month", Payment.created_at) == m_date.month,
                    func.extract("year", Payment.created_at) == m_date.year,
                    Payment.status == PaymentStatus.CONFIRMED,
                )
            )
        )).scalar_one()
        month_name = months_uz[m_date.month - 1][:3]
        income_trend.append({"month": month_name, "income": float(inc)})

        # Yangi o'quvchilar
        new_st_count = (await db.execute(
            select(func.count(Student.id)).where(
                and_(
                    func.extract("month", Student.created_at) == m_date.month,
                    func.extract("year", Student.created_at) == m_date.year,
                )
            )
        )).scalar_one()
        new_students_trend.append({"name": month_name, "count": new_st_count})

    # 2. Top 5 Guruhlar
    top_groups_query = (
        select(Group.name, func.count(Enrollment.id).label('student_count'))
        .outerjoin(Enrollment, and_(Enrollment.group_id == Group.id, Enrollment.status == EnrollmentStatus.ACTIVE))
        .where(Group.status == GroupStatus.ACTIVE)
        .group_by(Group.id)
        .order_by(func.count(Enrollment.id).desc())
        .limit(5)
    )
    top_groups = [{"name": r[0], "count": r[1]} for r in (await db.execute(top_groups_query)).all()]

    # 3. Top 5 O'qituvchilar
    top_teachers_query = (
        select(User.full_name, func.count(Enrollment.id).label('student_count'), User.photo_url)
        .join(Group, Group.teacher_id == User.id)
        .outerjoin(Enrollment, and_(Enrollment.group_id == Group.id, Enrollment.status == EnrollmentStatus.ACTIVE))
        .where(User.role == UserRole.TEACHER)
        .group_by(User.id)
        .order_by(func.count(Enrollment.id).desc())
        .limit(5)
    )
    top_teachers = [{"name": r[0], "count": r[1], "photo": r[2]} for r in (await db.execute(top_teachers_query)).all()]

    # 4. Top 5 O'quvchilar (Uyga vazifalar bo'yicha)
    from app.models.lesson import Grade, GradeType
    top_students_hw_query = (
        select(Student.full_name, func.coalesce(func.sum(Grade.score), 0).label('total_score'), Student.photo_url)
        .join(Grade, Grade.student_id == Student.id)
        .where(Grade.grade_type == GradeType.HOMEWORK)
        .group_by(Student.id)
        .order_by(func.sum(Grade.score).desc())
        .limit(5)
    )
    top_students_hw = [{"name": r[0], "score": float(r[1]), "photo": r[2]} for r in (await db.execute(top_students_hw_query)).all()]

    # 5. Qarzdorlar soni (Shu oy uchun aniq hisob)
    from sqlalchemy.orm import selectinload
    
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

    student_query = (
        select(Student)
        .options(
            selectinload(Student.enrollments).selectinload(Enrollment.group).selectinload(Group.course)
        )
        .where(
            Student.id.in_(
                select(Enrollment.student_id).where(Enrollment.status == EnrollmentStatus.ACTIVE)
            )
        )
    )
    enrolled_students = (await db.execute(student_query)).scalars().all()

    debtors_count = 0
    for s in enrolled_students:
        total_required = Decimal("0.00")
        for enr in s.enrollments:
            if enr.status == EnrollmentStatus.ACTIVE and enr.group and enr.group.course:
                course_fee = enr.group.course.monthly_fee
                discount = enr.discount_pct
                required = course_fee * (Decimal("1") - discount / Decimal("100"))
                total_required += required
                
        total_paid = paid_amounts.get(s.id, Decimal("0.00"))
        if total_required - total_paid > 0:
            debtors_count += 1

    # 6. Savdo Voronkasi (Real Data)
    lead_counts = (await db.execute(
        select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
    )).all()
    
    lead_stats = {status: 0 for status in LeadStatus}
    for status, count in lead_counts:
        lead_stats[status] = count

    leads_funnel = [
        {"name": "Yangi Lidlar", "count": lead_stats[LeadStatus.NEW], "color": "blue"},
        {"name": "Aloqaga chiqildi", "count": lead_stats[LeadStatus.CONTACTED], "color": "purple"},
        {"name": "Sinov darsida", "count": lead_stats[LeadStatus.TRIAL], "color": "yellow"},
        {"name": "Sotib oldi (Konversiya)", "count": lead_stats[LeadStatus.ENROLLED], "color": "emerald"},
    ]

    return {
        "active_students": student_count,
        "monthly_income": float(monthly_income),
        "monthly_expense": float(monthly_expense),
        "net_profit": float(Decimal(str(monthly_income)) - Decimal(str(monthly_expense))),
        "today_attendance_rate": today_att_rate,
        "today_lessons_count": len(today_lessons),
        "income_trend": income_trend,
        "new_students_trend": new_students_trend,
        "leads_funnel": leads_funnel,
        "top_groups": top_groups,
        "top_teachers": top_teachers,
        "top_students_hw": top_students_hw,
        "debtors_count": debtors_count,
    }

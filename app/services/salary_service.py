"""
Salary Service — Oylik maosh avtomatik hisoblash.
"""
import logging
from decimal import Decimal
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.user import User, UserRole
from app.models.finance import Salary, SalaryStatus
from app.models.iot import Attendance, AttendanceStatus
from app.models.lesson import Lesson
from app.models.academic import Group

logger = logging.getLogger(__name__)

# Sozlamalar (keyinchalik DB ga ko'chirish mumkin)
DEFAULT_BASE_SALARY = Decimal("3_000_000")  # 3 mln so'm
LESSON_BONUS = Decimal("50_000")            # Har bir dars uchun bonus
ABSENT_PENALTY = Decimal("100_000")         # Kechikish uchun jarima


async def auto_calculate_salary(
    db: AsyncSession,
    user_id: str,
    month: int,
    year: int,
) -> dict:
    """
    O'qituvchi maoshini avtomatik hisoblash:
    - Asosiy maosh: DEFAULT_BASE_SALARY
    - Bonus: o'tkazilgan darslar soni × LESSON_BONUS
    - Jarima: boshqa mezonlar asosida (kengaytirish mumkin)
    """
    import uuid
    uid = uuid.UUID(user_id)

    # Allaqachon hisoblangan bo'lsa
    existing = (await db.execute(
        select(Salary).where(
            and_(
                Salary.user_id == uid,
                Salary.period_month == month,
                Salary.period_year == year,
            )
        )
    )).scalar_one_or_none()

    if existing:
        logger.info(f"Maosh allaqachon hisoblangan: user={user_id} {month}/{year}")
        return {"status": "skipped", "reason": "already_exists", "salary_id": str(existing.id)}

    # O'sha oy o'tkazilgan darslar sonini hisoblash
    lesson_count_result = await db.execute(
        select(func.count(Lesson.id)).join(Group, Lesson.group_id == Group.id).where(
            and_(
                Group.teacher_id == uid,
                func.extract("month", Lesson.lesson_date) == month,
                func.extract("year", Lesson.lesson_date) == year,
                Lesson.is_cancelled == False,
            )
        )
    )
    lesson_count = lesson_count_result.scalar_one() or 0

    base = DEFAULT_BASE_SALARY
    bonus = LESSON_BONUS * lesson_count
    penalty = Decimal("0.00")

    salary = Salary(
        user_id=uid,
        period_month=month,
        period_year=year,
        base_amount=base,
        bonus_amount=bonus,
        penalty_amount=penalty,
        status=SalaryStatus.PENDING,
        comment=f"Avtomatik hisoblandi: {lesson_count} ta dars",
    )
    db.add(salary)
    await db.flush()

    total = base + bonus - penalty
    logger.info(f"Maosh hisoblandi: user={user_id}, total={total}, lessons={lesson_count}")
    return {
        "status": "created",
        "salary_id": str(salary.id),
        "base": float(base),
        "bonus": float(bonus),
        "penalty": float(penalty),
        "total": float(total),
        "lesson_count": lesson_count,
    }


async def calculate_all_teacher_salaries(db: AsyncSession, month: int, year: int) -> list:
    """Barcha aktiv o'qituvchilar maoshini hisoblash (Celery Beat uchun)."""
    teachers = (await db.execute(
        select(User).where(
            and_(User.role == UserRole.TEACHER, User.is_active == True)
        )
    )).scalars().all()

    results = []
    for teacher in teachers:
        result = await auto_calculate_salary(db, str(teacher.id), month, year)
        results.append({"user_id": str(teacher.id), "full_name": teacher.full_name, **result})

    await db.flush()
    return results

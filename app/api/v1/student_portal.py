from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from typing import Annotated
import uuid

from app.database import get_db
from app.models.student import Student
from app.models.academic import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson
from app.models.iot import Attendance
from app.models.finance import Payment
from app.core.dependencies import get_current_student

router = APIRouter(prefix="/student-portal", tags=["Student Portal"])

CurrentStudent = Annotated[Student, Depends(get_current_student)]


@router.get("/me", summary="O'quvchi ma'lumotlari")
async def get_my_profile(student: CurrentStudent):
    return {
        "id": str(student.id),
        "full_name": student.full_name,
        "phone": student.phone,
        "balance": float(student.balance),
        "status": student.status,
    }


@router.get("/enrollments", summary="O'quvchining joriy guruhlari va darslari")
async def get_my_enrollments(
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    # Guruhlar ro'yxati
    res = await db.execute(
        select(Enrollment)
        .options(selectinload(Enrollment.group))
        .where(Enrollment.student_id == student.id, Enrollment.status == EnrollmentStatus.ACTIVE)
    )
    enrollments = res.scalars().all()
    
    data = []
    for enr in enrollments:
        if not enr.group:
            continue
        data.append({
            "group_id": str(enr.group_id),
            "group_name": enr.group.name,
            "teacher_id": str(enr.group.teacher_id) if enr.group.teacher_id else None,
            "start_date": enr.group.start_date,
            "end_date": enr.group.end_date,
            "status": enr.group.status
        })
    return {"data": data}


@router.get("/attendance", summary="O'quvchining davomati")
async def get_my_attendance(
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50
):
    res = await db.execute(
        select(Attendance, Lesson.lesson_date, Lesson.topic)
        .join(Lesson, Attendance.lesson_id == Lesson.id)
        .where(Attendance.student_id == student.id)
        .order_by(Lesson.lesson_date.desc())
        .limit(limit)
    )
    
    rows = res.all()
    data = []
    for att, l_date, l_topic in rows:
        data.append({
            "lesson_date": l_date,
            "topic": l_topic,
            "status": att.status,
            "is_manual": att.is_manual
        })
    return {"data": data}


@router.get("/payments", summary="O'quvchining to'lovlari")
async def get_my_payments(
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50
):
    res = await db.execute(
        select(Payment)
        .where(Payment.student_id == student.id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )
    payments = res.scalars().all()
    return {"data": payments}

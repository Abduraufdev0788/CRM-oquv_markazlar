from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from typing import Annotated
import uuid

from app.database import get_db
from app.models.student import Student
from app.models.academic import Enrollment, EnrollmentStatus, Group, GroupStatus
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
        .join(Group, Enrollment.group_id == Group.id)
        .options(selectinload(Enrollment.group).selectinload(Group.course))
        .where(
            Enrollment.student_id == student.id, 
            Enrollment.status == EnrollmentStatus.ACTIVE,
            Group.status != GroupStatus.ARCHIVED
        )
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


@router.post("/homework/{hw_id}/submit", summary="Vazifani jo'natish")
async def submit_homework(
    hw_id: uuid.UUID,
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)],
    content_text: str | None = None,
    file_url: str | None = None,
):
    from app.models.lesson import Homework, HomeworkSubmission
    from fastapi import HTTPException
    
    hw = (await db.execute(select(Homework).where(Homework.id == hw_id))).scalar_one_or_none()
    if not hw:
        raise HTTPException(status_code=404, detail="Uy vazifasi topilmadi")
        
    # Tekshiramiz: oldin yuborganmi?
    existing = (await db.execute(
        select(HomeworkSubmission).where(
            and_(HomeworkSubmission.homework_id == hw_id, HomeworkSubmission.student_id == student.id)
        )
    )).scalar_one_or_none()
    
    if existing:
        existing.content_text = content_text
        existing.file_url = file_url
        await db.flush()
        await db.refresh(existing)
        return {"message": "Javob yangilandi", "data": {"id": existing.id}}
        
    submission = HomeworkSubmission(
        homework_id=hw_id,
        student_id=student.id,
        content_text=content_text,
        file_url=file_url
    )
    db.add(submission)
    await db.flush()
    await db.refresh(submission)
    return {"message": "Javob yuborildi", "data": {"id": submission.id}}

@router.get("/homeworks", summary="O'quvchining vazifalari")
async def get_my_homeworks(
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50
):
    from app.models.lesson import Homework, HomeworkSubmission
    
    # 1. O'quvchi o'qiyotgan guruhlarni topamiz
    group_ids_res = await db.execute(
        select(Enrollment.group_id).where(Enrollment.student_id == student.id, Enrollment.status == EnrollmentStatus.ACTIVE)
    )
    group_ids = [r for r in group_ids_res.scalars().all()]
    
    if not group_ids:
        return {"data": []}
        
    # 2. Shu guruhlarga tegishli darslarning vazifalarini topamiz
    res = await db.execute(
        select(Homework, Lesson.topic, Lesson.lesson_date, Group.name)
        .join(Lesson, Homework.lesson_id == Lesson.id)
        .join(Group, Lesson.group_id == Group.id)
        .where(Lesson.group_id.in_(group_ids))
        .order_by(Homework.created_at.desc())
        .limit(limit)
    )
    
    # 3. Yuborilgan javoblarni ham olib kelamiz
    subs_res = await db.execute(
        select(HomeworkSubmission).where(HomeworkSubmission.student_id == student.id)
    )
    my_subs = {sub.homework_id: sub for sub in subs_res.scalars().all()}
    
    data = []
    for hw, l_topic, l_date, g_name in res.all():
        sub = my_subs.get(hw.id)
        data.append({
            "id": hw.id,
            "title": hw.title,
            "description": hw.description,
            "due_date": hw.due_date,
            "max_score": hw.max_score,
            "lesson_topic": l_topic,
            "lesson_date": l_date,
            "group_name": g_name,
            "submitted": bool(sub),
            "submission_content": sub.content_text if sub else None,
            "submission_file": sub.file_url if sub else None,
        })
        
    return {"data": data}

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from typing import Annotated
import uuid

from app.database import get_db
from app.models.student import Student
from app.models.academic import Enrollment, EnrollmentStatus, Group, GroupStatus
from app.models.academic import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson, Homework, HomeworkSubmission
from app.models.iot import Attendance
from app.models.finance import Payment
from app.core.dependencies import get_current_student
from app.schemas.lesson import HomeworkSubmissionCreate, HomeworkSubmissionResponse

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
        "photo_url": student.photo_url,
    }


from pydantic import BaseModel
from typing import Optional

class ProfileUpdate(BaseModel):
    photo_url: Optional[str] = None

class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str

@router.put("/me/profile", summary="Profil rasmini yangilash")
async def update_profile(
    data: ProfileUpdate,
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    if data.photo_url is not None:
        student.photo_url = data.photo_url
        
    await db.commit()
    return {"detail": "Profil muvaffaqiyatli yangilandi"}

@router.put("/me/password", summary="Parolni o'zgartirish")
async def update_password(
    data: PasswordUpdate,
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from fastapi import HTTPException, status
    from app.core.security import verify_password, get_password_hash
    
    # Parol mantiqini tekshirish
    if student.password_hash:
        # Agar yangi parol o'rnatilgan bo'lsa
        if not verify_password(data.old_password, student.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Eski parol noto'g'ri",
            )
    else:
        # Eski usul (Tug'ilgan sana) bilan tekshirish
        valid_passwords = ["123456"]
        if student.birth_date:
            valid_passwords.append(student.birth_date.strftime("%Y-%m-%d"))
            valid_passwords.append(student.birth_date.strftime("%d%m%Y"))
            valid_passwords.append(student.birth_date.strftime("%d.%m.%Y"))

        if data.old_password not in valid_passwords:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Eski parol noto'g'ri",
            )
            
    student.password_hash = get_password_hash(data.new_password)
    await db.commit()
    
    return {"detail": "Parol muvaffaqiyatli o'zgartirildi"}


@router.get("/enrollments", summary="O'quvchining joriy guruhlari va darslari")
async def get_my_enrollments(
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    # Guruhlar ro'yxati
    res = await db.execute(
        select(Enrollment)
        .join(Group, Enrollment.group_id == Group.id)
        .options(
            selectinload(Enrollment.group).selectinload(Group.course),
            selectinload(Enrollment.group).selectinload(Group.teacher),
            selectinload(Enrollment.group).selectinload(Group.room)
        )
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
            "course_name": enr.group.course.name if enr.group.course else None,
            "monthly_fee": float(enr.group.course.monthly_fee) if enr.group.course else 0,
            "discount_pct": float(enr.discount_pct) if hasattr(enr, 'discount_pct') else 0,
            "teacher_id": str(enr.group.teacher_id) if enr.group.teacher_id else None,
            "teacher_name": enr.group.teacher.full_name if enr.group.teacher else "Ustoz biriktirilmagan",
            "room_name": enr.group.room.name if enr.group.room else "Xona yo'q",
            "start_date": enr.group.start_date,
            "end_date": enr.group.end_date,
            "status": enr.group.status,
            "schedule": enr.group.schedule
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


@router.get("/payments/{payment_id}/receipt", summary="To'lov chekini (PDF) yuklab olish")
async def download_receipt(
    payment_id: uuid.UUID,
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse
    from app.services.pdf_service import PDFService
    
    payment = (await db.execute(select(Payment).where(Payment.id == payment_id, Payment.student_id == student.id))).scalar_one_or_none()
    
    if not payment:
        raise HTTPException(status_code=404, detail="To'lov topilmadi")
        
    if payment.status != "confirmed":
        raise HTTPException(status_code=400, detail="Faqat tasdiqlangan to'lovlar uchun chek beriladi")
        
    # Generate PDF
    pdf_buffer = PDFService.generate_receipt(payment=payment, student_name=student.full_name, org_name="EduCRM O'quv Markazi")
    
    # Return as StreamingResponse
    return StreamingResponse(
        pdf_buffer, 
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=chek_{str(payment_id)[:8]}.pdf"}
    )


@router.post("/homeworks/{hw_id}/submit", response_model=HomeworkSubmissionResponse, summary="Uy vazifasini yuborish")
async def submit_homework(
    hw_id: uuid.UUID,
    data: HomeworkSubmissionCreate,
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from fastapi import HTTPException
    import datetime as dt

    # Vazifa haqiqatan borligini tekshirish
    hw = (await db.execute(select(Homework).where(Homework.id == hw_id))).scalar_one_or_none()
    if not hw:
        raise HTTPException(status_code=404, detail="Uy vazifasi topilmadi")

    if hw.due_date:
        now = dt.datetime.now(dt.timezone.utc)
        if isinstance(hw.due_date, dt.datetime):
            due = hw.due_date.replace(tzinfo=dt.timezone.utc) if hw.due_date.tzinfo is None else hw.due_date
        else:
            due = dt.datetime.combine(hw.due_date, dt.time.max, tzinfo=dt.timezone.utc)
        
        if now > due:
            raise HTTPException(status_code=400, detail="Vazifa topshirish muddati tugagan")

    # Oldin yuborilganligini tekshiramiz
    existing_sub = (await db.execute(
        select(HomeworkSubmission)
        .where(HomeworkSubmission.homework_id == hw_id, HomeworkSubmission.student_id == student.id)
    )).scalar_one_or_none()

    if existing_sub:
        # Yangilaymiz
        if data.content_text is not None:
            existing_sub.content_text = data.content_text
        if data.file_url is not None:
            existing_sub.file_url = data.file_url
        await db.commit()
        
        # O'quvchi ma'lumotlarini yuklash (schema uchun)
        existing_sub = (await db.execute(
            select(HomeworkSubmission)
            .options(selectinload(HomeworkSubmission.student))
            .where(HomeworkSubmission.id == existing_sub.id)
        )).scalar_one()
        return existing_sub
    else:
        # Yangi yaratamiz
        new_sub = HomeworkSubmission(
            homework_id=hw_id,
            student_id=student.id,
            content_text=data.content_text,
            file_url=data.file_url
        )
        db.add(new_sub)
        await db.commit()

        new_sub = (await db.execute(
            select(HomeworkSubmission)
            .options(selectinload(HomeworkSubmission.student))
            .where(HomeworkSubmission.id == new_sub.id)
        )).scalar_one()
        return new_sub


@router.get("/homeworks", summary="O'quvchining vazifalari")
async def get_my_homeworks(
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50
):
    from app.models.lesson import Homework, HomeworkSubmission, Grade, GradeType
    
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

    # 4. Baholarni olib kelamiz
    grades_res = await db.execute(
        select(Grade).where(Grade.student_id == student.id, Grade.grade_type == GradeType.HOMEWORK)
    )
    my_grades = {g.homework_id: g for g in grades_res.scalars().all()}
    
    data = []
    for hw, l_topic, l_date, g_name in res.all():
        sub = my_subs.get(hw.id)
        grade = my_grades.get(hw.id)
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
            "grade_score": float(grade.score) if grade else None,
            "grade_comment": grade.comment if grade else None,
        })
        
    return {"data": data}

@router.get("/materials", summary="O'quvchining o'quv materiallari")
async def get_my_materials(
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50
):
    from app.models.academic import Material
    
    # 1. O'quvchi o'qiyotgan guruhlarni topamiz
    group_ids_res = await db.execute(
        select(Enrollment.group_id).where(Enrollment.student_id == student.id, Enrollment.status == EnrollmentStatus.ACTIVE)
    )
    group_ids = [r for r in group_ids_res.scalars().all()]
    
    if not group_ids:
        return {"data": []}
        
    # 2. Shu guruhlarga tegishli materiallarni topamiz
    res = await db.execute(
        select(Material)
        .options(selectinload(Material.group), selectinload(Material.uploader))
        .where(Material.group_id.in_(group_ids))
        .order_by(Material.created_at.desc())
        .limit(limit)
    )
    materials = res.scalars().all()
    
    data = []
    for m in materials:
        data.append({
            "id": m.id,
            "title": m.title,
            "description": m.description,
            "file_url": m.file_url,
            "file_type": m.file_type,
            "created_at": m.created_at,
            "group_name": m.group.name if m.group else None,
            "uploader_name": m.uploader.full_name if m.uploader else "Tizim"
        })
    return {"data": data}

class SupportRequest(BaseModel):
    subject: str
    message: str

@router.post("/support", summary="Adminga murojaat yuborish (Qo'llab-quvvatlash)")
async def submit_support_ticket(
    data: SupportRequest,
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.user import User, UserRole
    from app.models.system import Notification, NotificationType, NotificationChannel, NotificationStatus

    # Barcha adminlarni topish
    res = await db.execute(select(User).where(User.role == UserRole.ADMIN))
    admins = res.scalars().all()

    notifications = []
    title = f"Yangi murojaat: {student.full_name}"
    body = f"Mavzu: {data.subject}\n\nXabar: {data.message}"

    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            student_id=student.id,
            channel=NotificationChannel.IN_APP,
            notif_type=NotificationType.GENERAL,
            title=title,
            body=body,
            status=NotificationStatus.SENT
        )
        notifications.append(notif)

    if notifications:
        db.add_all(notifications)
        await db.commit()

    return {"detail": "Murojaat muvaffaqiyatli yuborildi"}


from app.models.system import Notification, NotificationChannel

@router.get("/notifications", summary="O'quvchining bildirishnomalari")
async def get_my_notifications(
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    query = (
        select(Notification)
        .where(
            Notification.student_id == student.id,
            Notification.channel == NotificationChannel.IN_APP
        )
        .order_by(Notification.created_at.desc())
        .limit(20)
    )
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return [
        {
            "id": str(n.id),
            "title": n.title,
            "body": n.body,
            "is_read": n.is_read,
            "type": n.notif_type.value,
            "created_at": n.created_at
        }
        for n in notifications
    ]

@router.put("/notifications/{notification_id}/read", summary="Bitta xabarni o'qilgan deb belgilash")
async def mark_as_read(
    notification_id: str,
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from fastapi import HTTPException
    query = select(Notification).where(
        Notification.id == notification_id,
        Notification.student_id == student.id
    )
    notif = (await db.execute(query)).scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Xabar topilmadi")
    
    notif.is_read = True
    await db.commit()
    return {"success": True}

@router.put("/notifications/read-all", summary="Barcha o'qilmagan xabarlarni o'qilgan deb belgilash")
async def mark_all_as_read(
    student: CurrentStudent,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from sqlalchemy import update
    await db.execute(
        update(Notification)
        .where(
            Notification.student_id == student.id,
            Notification.is_read == False,
            Notification.channel == NotificationChannel.IN_APP
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"success": True}

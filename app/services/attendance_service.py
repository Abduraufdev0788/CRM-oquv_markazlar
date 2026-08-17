"""
Attendance Service — Face ID logini Attendance ga aylantirish biznes logikasi.
"""
import logging
from datetime import datetime, timezone, time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.iot import FaceLog, FaceDevice, Attendance, AttendanceStatus
from app.models.student import Student
from app.models.lesson import Lesson
from app.models.academic import Group, Enrollment, EnrollmentStatus

logger = logging.getLogger(__name__)

# Necha daqiqadan keyin LATE hisoblanadi
LATE_THRESHOLD_MINUTES = 10


async def process_face_log_to_attendance(db: AsyncSession, face_log_id: str) -> dict:
    """
    FaceLog → Attendance oqimi:
    1. face_data_id orqali o'quvchini topamiz
    2. Hozirgi vaqtda bo'layotgan darsni topamiz
    3. O'quvchi o'sha guruhda yozilganligini tekshiramiz
    4. PRESENT yoki LATE holat bilan Attendance yaratamiz
    5. Ota-onaga xabarnoma yuboramiz
    """
    import uuid
    face_log = (await db.execute(
        select(FaceLog).where(FaceLog.id == uuid.UUID(face_log_id))
    )).scalar_one_or_none()

    if not face_log:
        logger.error(f"FaceLog topilmadi: {face_log_id}")
        return {"status": "error", "reason": "face_log_not_found"}

    if face_log.is_processed:
        return {"status": "skipped", "reason": "already_processed"}

    # O'quvchini topish
    student = (await db.execute(
        select(Student).where(Student.face_data_id == face_log.face_data_id)
    )).scalar_one_or_none()

    if not student:
        face_log.error_message = f"face_data_id={face_log.face_data_id} bo'yicha o'quvchi topilmadi"
        face_log.is_processed = True
        await db.flush()
        logger.warning(f"O'quvchi topilmadi: {face_log.face_data_id}")
        return {"status": "error", "reason": "student_not_found"}

    logged_at: datetime = face_log.logged_at
    log_time: time = logged_at.time()
    log_date = logged_at.date()

    # Hozirgi vaqtda bo'layotgan darsni topish (o'quvchi yozilgan guruhlar bo'yicha)
    active_enrollments = (await db.execute(
        select(Enrollment).where(
            and_(
                Enrollment.student_id == student.id,
                Enrollment.status == EnrollmentStatus.ACTIVE,
            )
        )
    )).scalars().all()

    group_ids = [e.group_id for e in active_enrollments]
    if not group_ids:
        face_log.error_message = "O'quvchining aktiv guruhi yo'q"
        face_log.is_processed = True
        await db.flush()
        return {"status": "error", "reason": "no_active_enrollments"}

    # Bugungi darsni topish
    lesson = (await db.execute(
        select(Lesson).where(
            and_(
                Lesson.group_id.in_(group_ids),
                Lesson.lesson_date == log_date,
                Lesson.start_time <= log_time,
                Lesson.end_time >= log_time,
                Lesson.is_cancelled == False,
            )
        )
    )).scalar_one_or_none()

    if not lesson:
        face_log.error_message = f"Bugungi dars topilmadi (vaqt: {log_time})"
        face_log.is_processed = True
        await db.flush()
        return {"status": "error", "reason": "lesson_not_found"}

    # Takroriy qayd etilishni tekshirish
    existing_att = (await db.execute(
        select(Attendance).where(
            and_(
                Attendance.student_id == student.id,
                Attendance.lesson_id == lesson.id,
            )
        )
    )).scalar_one_or_none()

    if existing_att:
        face_log.is_processed = True
        await db.flush()
        return {"status": "skipped", "reason": "already_marked"}

    # LATE yoki PRESENT aniqlash
    lesson_start = datetime.combine(log_date, lesson.start_time)
    diff_minutes = int((logged_at.replace(tzinfo=None) - lesson_start).total_seconds() / 60)
    att_status = AttendanceStatus.LATE if diff_minutes > LATE_THRESHOLD_MINUTES else AttendanceStatus.PRESENT
    late_minutes = max(0, diff_minutes) if att_status == AttendanceStatus.LATE else None

    attendance = Attendance(
        student_id=student.id,
        lesson_id=lesson.id,
        status=att_status,
        check_in_time=log_time,
        late_minutes=late_minutes,
        face_log_id=face_log.id,
        is_manual=False,
    )
    db.add(attendance)
    face_log.is_processed = True
    await db.flush()

    logger.info(f"Attendance yaratildi: student={student.full_name}, status={att_status}")
    return {
        "status": "success",
        "student_id": str(student.id),
        "lesson_id": str(lesson.id),
        "attendance_status": att_status,
        "late_minutes": late_minutes,
    }

"""
Notification Service — Telegram va SMS xabarnomalar yuborish.
"""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.system import Notification, NotificationChannel, NotificationStatus, NotificationType
from app.models.student import Student, Parent
from app.config import settings

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    *,
    parent_id: Optional[str] = None,
    student_id: Optional[str] = None,
    channel: NotificationChannel,
    notif_type: NotificationType,
    title: str,
    body: str,
) -> Notification:
    """Notification yozuvini yaratib DB ga saqlaydi."""
    import uuid
    notif = Notification(
        parent_id=uuid.UUID(parent_id) if parent_id else None,
        student_id=uuid.UUID(student_id) if student_id else None,
        channel=channel,
        notif_type=notif_type,
        title=title,
        body=body,
        status=NotificationStatus.PENDING,
    )
    db.add(notif)
    await db.flush()
    return notif


async def send_attendance_notification(db: AsyncSession, student_id: str, status: str, lesson_id: str = None) -> None:
    """
    O'quvchi davomati haqida ota-onaga xabarnoma yuboradi.
    """
    import uuid
    import httpx
    from app.models.system import NotificationStatus
    from datetime import datetime, timezone

    student = (await db.execute(
        select(Student).where(Student.id == uuid.UUID(student_id))
    )).scalar_one_or_none()

    if not student or not student.parent_id:
        logger.warning(f"O'quvchi yoki ota-onasi topilmadi: {student_id}")
        return

    parent = (await db.execute(
        select(Parent).where(Parent.id == student.parent_id)
    )).scalar_one_or_none()

    if not parent:
        return

    lesson_info = ""
    if lesson_id:
        from app.models.lesson import Lesson
        from sqlalchemy.orm import selectinload
        lesson = (await db.execute(
            select(Lesson).options(selectinload(Lesson.group)).where(Lesson.id == uuid.UUID(lesson_id))
        )).scalar_one_or_none()
        
        if lesson:
            date_str = lesson.lesson_date.strftime("%d.%m.%Y")
            start_str = lesson.start_time.strftime("%H:%M")
            end_str = lesson.end_time.strftime("%H:%M")
            group_name = lesson.group.name if lesson.group else "Noma'lum guruh"
            lesson_info = f"📚 Guruh: {group_name}\n📅 Sana: {date_str}\n⏰ Vaqt: {start_str} - {end_str}\n\n"

    status_text = {
        "present": "✅ Darsga keldi",
        "late": "⚠️ Kechikib keldi",
        "absent": "❌ Darsga kelmadi",
        "excused": "📋 Sababli yo'q",
    }.get(status, status)

    title = f"Davomat: {student.full_name}"
    body = f"👦 O'quvchi: {student.full_name}\n\n{lesson_info}Holati: {status_text}"

    channel = NotificationChannel.TELEGRAM if parent.telegram_id else NotificationChannel.SMS
    notif = await create_notification(
        db,
        parent_id=str(parent.id),
        student_id=student_id,
        channel=channel,
        notif_type=NotificationType.ATTENDANCE,
        title=title,
        body=body,
    )
    await db.flush()

    await db.flush()

    # Celery yoqilmagan bo'lishi mumkinligi uchun to'g'ridan to'g'ri Telegram API ga yuboramiz
    if channel == NotificationChannel.TELEGRAM and parent.telegram_id:
        try:
            text = f"*{title}*\n\n{body}"
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json={
                    "chat_id": parent.telegram_id,
                    "text": text,
                    "parse_mode": "Markdown",
                }, timeout=10.0)
                if resp.status_code == 200:
                    notif.status = NotificationStatus.SENT
                    notif.sent_at = datetime.now(timezone.utc)
                    notif.external_id = str(resp.json()["result"]["message_id"])
                    logger.info(f"Telegram orqali ota-onaga xabar ketdi: {parent.telegram_id}")
        except Exception as e:
            logger.error(f"Xabar yuborishda xato: {e}")


async def send_payment_due_notification(db: AsyncSession, student_id: str, amount: float) -> None:
    """To'lov muddati o'tganda ota-onaga eslatma."""
    import uuid
    from app.tasks.notification_tasks import send_telegram_notification

    student = (await db.execute(
        select(Student).where(Student.id == uuid.UUID(student_id))
    )).scalar_one_or_none()

    if not student or not student.parent_id:
        return

    notif = await create_notification(
        db,
        parent_id=str(student.parent_id),
        student_id=student_id,
        channel=NotificationChannel.TELEGRAM,
        notif_type=NotificationType.PAYMENT_DUE,
        title=f"To'lov eslatmasi: {student.full_name}",
        body=f"💳 {student.full_name} uchun {amount:,.0f} so'm to'lov amalga oshirilmagan.",
    )
    await db.flush()
    send_telegram_notification.delay(str(notif.id))

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


async def send_attendance_notification(db: AsyncSession, student_id: str, status: str) -> None:
    """
    O'quvchi davomati haqida ota-onaga xabarnoma yuboradi.
    1. O'quvchi → Parent → telegram_id topiladi
    2. Notification yaratiladi
    3. Celery task orqali yuboriladi
    """
    import uuid
    from app.tasks.notification_tasks import send_telegram_notification

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

    status_text = {
        "present": "✅ Darsga keldi",
        "late": "⚠️ Kechikib keldi",
        "absent": "❌ Darsga kelmadi",
        "excused": "📋 Sababli yo'q",
    }.get(status, status)

    title = f"Davomat: {student.full_name}"
    body = f"{student.full_name} — {status_text}"

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

    # Celery orqali asinxron yuborish
    send_telegram_notification.delay(str(notif.id))
    logger.info(f"Notification Celery ga yuborildi: {notif.id}")


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

"""
Notification background tasks — Telegram va SMS yuborish.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_telegram_notification(self, notification_id: str) -> dict:
    """
    Notification jadvalidagi yozuvni Telegram orqali yuboradi.
    Muvaffaqiyatsiz bo'lsa 3 marta qayta urinadi.
    """
    try:
        # TODO: Telegram Bot API integratsiyasi
        logger.info(f"Sending Telegram notification: {notification_id}")
        return {"status": "sent", "notification_id": notification_id}
    except Exception as exc:
        logger.error(f"Telegram send failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_sms_notification(self, notification_id: str) -> dict:
    """
    Notification jadvalidagi yozuvni SMS orqali yuboradi.
    """
    try:
        # TODO: Eskiz.uz yoki Playmobile integratsiyasi
        logger.info(f"Sending SMS notification: {notification_id}")
        return {"status": "sent", "notification_id": notification_id}
    except Exception as exc:
        logger.error(f"SMS send failed: {exc}")
        raise self.retry(exc=exc)


@shared_task
def process_face_log(face_log_id: str) -> dict:
    """
    FaceLog yozuvini tahlil qilib Attendance yaratadi,
    keyin ota-onaga xabarnoma yuboradi.
    """
    logger.info(f"Processing face log: {face_log_id}")
    # TODO: FaceLog → Attendance → Notification oqimi
    return {"status": "processed", "face_log_id": face_log_id}


@shared_task
def notify_parent_attendance(student_id: str, attendance_status: str) -> dict:
    """Ota-onaga o'quvchi davomati haqida xabar yuboradi."""
    logger.info(f"Notifying parent for student {student_id}: {attendance_status}")
    # TODO: Parent telegram_id ni olish va xabar yuborish
    return {"student_id": student_id, "status": attendance_status}


@shared_task
def send_payment_reminders() -> dict:
    """Har kuni to'lov muddati o'tgan o'quvchilar uchun eslatma."""
    logger.info("Running daily payment reminders...")
    # TODO: Muddati o'tgan to'lovlarni topib ota-onalarga xabar berish
    return {"status": "completed"}

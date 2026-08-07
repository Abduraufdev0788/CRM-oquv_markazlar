"""
Notification background tasks — Telegram va SMS yuborish.
Servislar bilan to'liq integratsiya qilingan.
"""
import asyncio
import logging
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select, and_

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_sync_session():
    """Celery task ichida sync DB session olish."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    # Celery sync task uchun sync driver ishlatamiz
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="tasks.send_telegram")
def send_telegram_notification(self, notification_id: str) -> dict:
    """
    Notification jadvalidagi yozuvni Telegram orqali yuboradi.
    Muvaffaqiyatsiz bo'lsa 3 marta qayta urinadi (60 soniya interval).
    """
    import httpx
    from app.config import settings

    db = _get_sync_session()
    try:
        from app.models.system import Notification, NotificationStatus
        from app.models.student import Parent
        import uuid

        notif = db.query(Notification).filter(
            Notification.id == uuid.UUID(notification_id)
        ).first()

        if not notif:
            return {"status": "error", "reason": "notification_not_found"}

        if notif.status == NotificationStatus.SENT:
            return {"status": "skipped", "reason": "already_sent"}

        # Ota-onaning telegram_id sini olish
        parent = db.query(Parent).filter(Parent.id == notif.parent_id).first()
        if not parent or not parent.telegram_id:
            notif.status = NotificationStatus.FAILED
            notif.error_message = "Ota-onaning Telegram ID si yo'q"
            db.commit()
            return {"status": "error", "reason": "no_telegram_id"}

        # Telegram Bot API ga yuborish
        text = f"*{notif.title}*\n\n{notif.body}"
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        response = httpx.post(url, json={
            "chat_id": parent.telegram_id,
            "text": text,
            "parse_mode": "Markdown",
        }, timeout=10.0)

        if response.status_code == 200:
            data = response.json()
            notif.status = NotificationStatus.SENT
            notif.sent_at = datetime.now(timezone.utc)
            notif.external_id = str(data["result"]["message_id"])
            db.commit()
            logger.info(f"Telegram xabari yuborildi: {notification_id}")
            return {"status": "sent", "message_id": notif.external_id}
        else:
            raise Exception(f"Telegram API xatosi: {response.status_code} — {response.text}")

    except Exception as exc:
        logger.error(f"Telegram yuborishda xato: {exc}")
        try:
            from app.models.system import Notification, NotificationStatus
            import uuid
            notif = db.query(Notification).filter(
                Notification.id == uuid.UUID(notification_id)
            ).first()
            if notif:
                notif.error_message = str(exc)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="tasks.send_sms")
def send_sms_notification(self, notification_id: str) -> dict:
    """SMS Gateway (Eskiz.uz) orqali xabar yuborish."""
    import httpx
    from app.config import settings

    db = _get_sync_session()
    try:
        from app.models.system import Notification, NotificationStatus
        from app.models.student import Parent
        import uuid

        notif = db.query(Notification).filter(
            Notification.id == uuid.UUID(notification_id)
        ).first()
        if not notif:
            return {"status": "error", "reason": "not_found"}

        parent = db.query(Parent).filter(Parent.id == notif.parent_id).first()
        if not parent:
            return {"status": "error", "reason": "no_parent"}

        # Eskiz.uz API
        response = httpx.post(
            "https://notify.eskiz.uz/api/message/sms/send",
            headers={"Authorization": f"Bearer {settings.SMS_API_KEY}"},
            json={
                "mobile_phone": parent.phone.replace("+", ""),
                "message": notif.body,
                "from": settings.SMS_SENDER,
            },
            timeout=10.0,
        )

        if response.status_code == 200:
            notif.status = NotificationStatus.SENT
            notif.sent_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "sent"}
        else:
            raise Exception(f"SMS API xatosi: {response.status_code}")

    except Exception as exc:
        logger.error(f"SMS yuborishda xato: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="tasks.process_face_log")
def process_face_log(face_log_id: str) -> dict:
    """
    FaceLog ni tahlil qilib Attendance yaratadi,
    keyin ota-onaga xabarnoma yuboradi.
    Sinxron wrapper — ichida asyncio.run() ishlatiladi.
    """
    async def _async_process():
        from app.database import AsyncSessionLocal
        from app.services.attendance_service import process_face_log_to_attendance
        from app.services.notification_service import send_attendance_notification

        async with AsyncSessionLocal() as db:
            result = await process_face_log_to_attendance(db, face_log_id)
            await db.commit()

            if result["status"] == "success":
                await send_attendance_notification(
                    db,
                    student_id=result["student_id"],
                    status=result["attendance_status"],
                )
                await db.commit()

            return result

    return asyncio.run(_async_process())


@celery_app.task(name="tasks.send_payment_reminders")
def send_payment_reminders() -> dict:
    """Har kuni to'lov muddati o'tgan o'quvchilarga eslatma yuboradi."""
    async def _async_reminders():
        from datetime import date
        from app.database import AsyncSessionLocal
        from app.services.notification_service import send_payment_due_notification
        from sqlalchemy import select, and_
        from app.models.student import Student, StudentStatus
        from app.models.academic import Enrollment, EnrollmentStatus
        from app.models.finance import Payment, PaymentStatus

        today = date.today()
        month, year = today.month, today.year

        async with AsyncSessionLocal() as db:
            paid_sq = (
                select(Payment.student_id)
                .where(and_(
                    Payment.period_month == month,
                    Payment.period_year == year,
                    Payment.status == PaymentStatus.CONFIRMED,
                ))
                .scalar_subquery()
            )
            debtors = (await db.execute(
                select(Student).where(
                    and_(
                        Student.status == StudentStatus.ACTIVE,
                        Student.id.not_in(paid_sq),
                        Student.id.in_(
                            select(Enrollment.student_id)
                            .where(Enrollment.status == EnrollmentStatus.ACTIVE)
                        ),
                    )
                )
            )).scalars().all()

            count = 0
            for student in debtors:
                await send_payment_due_notification(db, str(student.id), 0)
                count += 1
            await db.commit()
            return {"sent": count}

    result = asyncio.run(_async_reminders())
    logger.info(f"To'lov eslatmasi: {result['sent']} ta yuborildi")
    return result

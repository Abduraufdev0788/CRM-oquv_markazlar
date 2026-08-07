"""
Celery application configuration.
Broker: Redis
Backend: Redis
"""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "educrm",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.notification_tasks",
        "app.tasks.report_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tashkent",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Task crash bo'lsa qayta ishlanadi
    worker_prefetch_multiplier=1,

    # ── Beat Schedule (Davriy vazifalar) ───────────────────────────────────────
    beat_schedule={
        # Har kuni soat 09:00 da to'lov eslatmasi
        "daily-payment-reminders": {
            "task": "app.tasks.notification_tasks.send_payment_reminders",
            "schedule": 86400.0,  # 24 soat
        },
        # Har oyning 1-sida maosh hisoblash
        "monthly-salary-report": {
            "task": "app.tasks.report_tasks.generate_monthly_salary_report",
            "schedule": 2592000.0,  # 30 kun
        },
    },
)

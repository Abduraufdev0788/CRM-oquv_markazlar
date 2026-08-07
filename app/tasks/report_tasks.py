"""
Report generation background tasks.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def generate_monthly_salary_report() -> dict:
    """Oylik maosh hisobotini yaratadi va Admin ga yuboradi."""
    logger.info("Generating monthly salary report...")
    # TODO: Maosh hisobot generatsiyasi
    return {"status": "generated"}


@shared_task
def generate_attendance_report(group_id: str, month: int, year: int) -> dict:
    """Guruh bo'yicha davomat hisobotini yaratadi."""
    logger.info(f"Generating attendance report for group {group_id} {month}/{year}")
    # TODO: Davomat hisobot generatsiyasi (PDF/Excel)
    return {"group_id": group_id, "month": month, "year": year}

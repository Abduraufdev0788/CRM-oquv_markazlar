# app/services package
from app.services.attendance_service import process_face_log_to_attendance
from app.services.notification_service import (
    create_notification,
    send_attendance_notification,
    send_payment_due_notification,
)
from app.services.salary_service import auto_calculate_salary, calculate_all_teacher_salaries
from app.services.report_service import get_dashboard_stats

__all__ = [
    "process_face_log_to_attendance",
    "create_notification",
    "send_attendance_notification",
    "send_payment_due_notification",
    "auto_calculate_salary",
    "calculate_all_teacher_salaries",
    "get_dashboard_stats",
]

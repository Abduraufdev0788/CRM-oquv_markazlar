from fastapi import APIRouter

from app.api.v1 import (
    auth, users, parents, students,
    groups, lessons, finance,
    attendance, reports, dashboard,
    student_portal, upload, materials, tests,
    notifications, leads
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(users.router)
api_router.include_router(parents.router)
api_router.include_router(students.router)
api_router.include_router(groups.router)
api_router.include_router(lessons.router)
api_router.include_router(finance.router)
api_router.include_router(attendance.router)
api_router.include_router(reports.router)
api_router.include_router(student_portal.router)
api_router.include_router(upload.router)
api_router.include_router(materials.router)
api_router.include_router(tests.router)
api_router.include_router(notifications.router)
api_router.include_router(leads.router)

from fastapi import APIRouter

from app.api.v1 import (
    auth, users, parents, students,
    groups, lessons, finance,
    attendance, face, reports, dashboard,
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
api_router.include_router(face.router)
api_router.include_router(reports.router)

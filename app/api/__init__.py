from fastapi import APIRouter

# Barcha v1 routerlarni shu fayldan import qilish
from app.api.v1 import auth, students, face

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(students.router)
api_router.include_router(face.router)

# TODO: Keyingi bosqichda qo'shiladi:
# from app.api.v1 import users, groups, attendance, finance, reports
# api_router.include_router(users.router)
# api_router.include_router(groups.router)
# api_router.include_router(attendance.router)
# api_router.include_router(finance.router)
# api_router.include_router(reports.router)

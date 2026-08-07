"""
Dashboard API — /api/v1/dashboard/
Bosh sahifa statistikasi.
"""
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.core.dependencies import require_roles
from app.services.report_service import get_dashboard_stats

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

ManagerOrAdmin = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))


@router.get("/", summary="Bosh sahifa statistikasi")
async def dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    """
    Qaytaradi:
    - Aktiv o'quvchilar soni
    - Bu oy tushumi
    - Bu oy xarajati
    - Sof foyda
    - Bugungi davomat foizi
    - Bugungi darslar soni
    """
    return await get_dashboard_stats(db)

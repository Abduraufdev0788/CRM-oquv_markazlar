from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.lead import Lead
from app.schemas.lead import LeadCreate, LeadUpdate, LeadResponse
from app.models.user import User, UserRole
from app.core.dependencies import require_roles

router = APIRouter(prefix="/leads", tags=["Leads"])

ManagerOrAdmin = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_in: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = ManagerOrAdmin,
) -> Any:
    """Yangi lid qo'shish."""
    new_lead = Lead(**lead_in.model_dump())
    db.add(new_lead)
    await db.commit()
    await db.refresh(new_lead)
    return new_lead


@router.get("/", response_model=List[LeadResponse])
async def get_leads(
    db: AsyncSession = Depends(get_db),
    current_user: User = ManagerOrAdmin,
) -> Any:
    """Barcha lidlarni ro'yxatini olish."""
    query = select(Lead).order_by(Lead.created_at.desc())
    result = await db.execute(query)
    leads = result.scalars().all()
    return leads


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = ManagerOrAdmin,
) -> Any:
    """Bitta lid haqida ma'lumot olish."""
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lid topilmadi")
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: UUID,
    lead_in: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = ManagerOrAdmin,
) -> Any:
    """Lidni yangilash."""
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lid topilmadi")

    update_data = lead_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)

    await db.commit()
    await db.refresh(lead)
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = ManagerOrAdmin,
) -> None:
    """Lidni o'chirish."""
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lid topilmadi")

    await db.delete(lead)
    await db.commit()

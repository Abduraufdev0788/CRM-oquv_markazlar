import uuid
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User, UserRole
from app.models.academic import Material, Group, Enrollment
from app.core.dependencies import require_roles, get_current_user
from app.schemas.academic import MaterialCreate, MaterialResponse
from app.schemas.base import PaginatedResponse, MessageResponse

router = APIRouter(prefix="/materials", tags=["Materials (O'quv materiallari)"])

AnyStaff = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TEACHER))


@router.post("/", response_model=MaterialResponse, status_code=201, summary="Yangi material yuklash")
async def create_material(
    data: MaterialCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    # Check if group exists and if teacher has access
    group = (await db.execute(select(Group).where(Group.id == data.group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
        
    if current_user.role == UserRole.TEACHER and group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Siz faqat o'zingizning guruhingizga material yuklay olasiz")

    material = Material(
        **data.model_dump(),
        uploaded_by=current_user.id
    )
    db.add(material)
    await db.commit()
    
    # Reload with relationships
    material = (await db.execute(
        select(Material)
        .options(
            selectinload(Material.uploader), 
            selectinload(Material.group).selectinload(Group.course),
            selectinload(Material.group).selectinload(Group.room)
        )
        .where(Material.id == material.id)
    )).scalar_one()
    
    return material


@router.get("/", response_model=PaginatedResponse[MaterialResponse], summary="Materiallar ro'yxati")
async def list_materials(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    group_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    query = select(Material).options(
        selectinload(Material.uploader), 
        selectinload(Material.group).selectinload(Group.course),
        selectinload(Material.group).selectinload(Group.room)
    )
    
    # Filters based on role
    if current_user.role == UserRole.TEACHER:
        # Teacher sees materials for their groups, or materials they uploaded
        teacher_groups = (await db.execute(select(Group.id).where(Group.teacher_id == current_user.id))).scalars().all()
        query = query.where(or_(Material.group_id.in_(teacher_groups), Material.uploaded_by == current_user.id))
        
    elif current_user.role == UserRole.STUDENT:
        # Student sees materials for their enrolled groups
        student_groups = (await db.execute(
            select(Enrollment.group_id).where(Enrollment.student_id == current_user.id)
        )).scalars().all()
        query = query.where(Material.group_id.in_(student_groups))
        
    if group_id:
        query = query.where(Material.group_id == group_id)
        
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    materials = (await db.execute(query.offset(skip).limit(limit).order_by(Material.created_at.desc()))).scalars().all()
    
    return PaginatedResponse.create(data=materials, total=total, skip=skip, limit=limit)


@router.delete("/{material_id}", response_model=MessageResponse, summary="Materialni o'chirish")
async def delete_material(
    material_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    material = (await db.execute(
        select(Material).options(selectinload(Material.group)).where(Material.id == material_id)
    )).scalar_one_or_none()
    
    if not material:
        raise HTTPException(status_code=404, detail="Material topilmadi")
        
    if current_user.role == UserRole.TEACHER:
        if material.uploaded_by != current_user.id and material.group.teacher_id != current_user.id:
            raise HTTPException(status_code=403, detail="Siz bu materialni o'chira olmaysiz")
            
    await db.delete(material)
    await db.commit()
    
    return MessageResponse(detail="Material muvaffaqiyatli o'chirildi")

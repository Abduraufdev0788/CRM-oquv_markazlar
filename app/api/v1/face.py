"""
Face ID Devices Admin CRUD + Webhook — /api/v1/face/
"""
import uuid
import secrets
from datetime import datetime, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User, UserRole
from app.models.iot import FaceDevice, FaceLog, DeviceStatus
from app.core.dependencies import require_roles
from app.schemas import (
    FaceDeviceCreate, FaceDeviceUpdate, FaceDeviceResponse,
    FaceWebhookPayload, FaceLogResponse,
    PaginatedResponse, MessageResponse,
)
from app.tasks.notification_tasks import process_face_log

router = APIRouter(prefix="/face", tags=["IoT / Face ID"])

AdminOnly = Depends(require_roles(UserRole.ADMIN))
ManagerOrAdmin = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICES
# ═══════════════════════════════════════════════════════════════════════════════
@router.get(
    "/devices",
    response_model=PaginatedResponse[FaceDeviceResponse],
    summary="Face ID qurilmalar ro'yxati",
)
async def list_devices(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
    dev_status: Optional[DeviceStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    query = select(FaceDevice)
    if dev_status:
        query = query.where(FaceDevice.status == dev_status)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    devices = (await db.execute(query.offset(skip).limit(limit))).scalars().all()
    return PaginatedResponse.create(data=devices, total=total, skip=skip, limit=limit)


@router.post(
    "/devices",
    response_model=FaceDeviceResponse,
    status_code=201,
    summary="Yangi Face ID qurilma qo'shish",
)
async def create_device(
    data: FaceDeviceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    # IP va serial_number takrorlanmasligini tekshirish
    existing_ip = (await db.execute(
        select(FaceDevice).where(FaceDevice.ip_address == data.ip_address)
    )).scalar_one_or_none()
    if existing_ip:
        raise HTTPException(status_code=409, detail="Bu IP manzil allaqachon ro'yxatda bor")

    existing_sn = (await db.execute(
        select(FaceDevice).where(FaceDevice.serial_number == data.serial_number)
    )).scalar_one_or_none()
    if existing_sn:
        raise HTTPException(status_code=409, detail="Bu serial raqam allaqachon ro'yxatda bor")

    device = FaceDevice(**data.model_dump())
    db.add(device)
    await db.flush()
    await db.refresh(device)
    return device


@router.get("/devices/{device_id}", response_model=FaceDeviceResponse, summary="Qurilma ma'lumoti")
async def get_device(
    device_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    device = (await db.execute(select(FaceDevice).where(FaceDevice.id == device_id))).scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Qurilma topilmadi")
    return device


@router.put("/devices/{device_id}", response_model=FaceDeviceResponse, summary="Qurilmani yangilash")
async def update_device(
    device_id: uuid.UUID,
    data: FaceDeviceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    device = (await db.execute(select(FaceDevice).where(FaceDevice.id == device_id))).scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Qurilma topilmadi")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(device, key, value)
    await db.flush()
    await db.refresh(device)
    return device


@router.post(
    "/devices/{device_id}/regenerate-secret",
    response_model=dict,
    summary="Qurilma API secret ni yangilash",
)
async def regenerate_device_secret(
    device_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    device = (await db.execute(select(FaceDevice).where(FaceDevice.id == device_id))).scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Qurilma topilmadi")

    new_secret = secrets.token_urlsafe(32)
    device.api_secret = new_secret
    await db.flush()
    # Yangi secretni faqat bir marta ko'rsatamiz — DB da hash saqlash kerak bo'lishi mumkin
    return {
        "detail": "Secret yangilandi. Uni qurilmaga kiriting va saqlab qo'ying!",
        "new_secret": new_secret,
    }


@router.delete("/devices/{device_id}", response_model=MessageResponse, summary="Qurilmani o'chirish")
async def delete_device(
    device_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AdminOnly],
):
    device = (await db.execute(select(FaceDevice).where(FaceDevice.id == device_id))).scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Qurilma topilmadi")
    await db.delete(device)
    return MessageResponse(detail=f"'{device.name}' qurilmasi o'chirildi")


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK
# ═══════════════════════════════════════════════════════════════════════════════
@router.post("/webhook", summary="Face ID qurilmadan log qabul qilish (webhook)")
async def face_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_device_secret: str = Header(..., description="Qurilma API secret"),
):
    """
    Face ID qurilma har safar yuz taniganda shu endpointga POST yuboradi.
    Body: FaceWebhookPayload formatida JSON.
    Header: X-Device-Secret: <api_secret>
    """
    payload_data = await request.json()

    # Qurilmani secret orqali autentifikatsiya qilish
    device = (await db.execute(
        select(FaceDevice).where(FaceDevice.api_secret == x_device_secret)
    )).scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=401, detail="Noto'g'ri qurilma yoki secret")

    # last_ping ni yangilash
    device.last_ping = datetime.now(timezone.utc)
    device.status = DeviceStatus.ONLINE

    # Payload validatsiyasi
    try:
        payload = FaceWebhookPayload(**payload_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Payload formati noto'g'ri: {e}")

    # Xom logni saqlash
    face_log = FaceLog(
        device_id=device.id,
        face_data_id=payload.face_id,
        raw_payload=payload_data,
        logged_at=datetime.fromisoformat(payload.timestamp),
        received_at=datetime.now(timezone.utc),
    )
    db.add(face_log)
    await db.flush()

    # Asinxron tahlil (Celery)
    process_face_log.delay(str(face_log.id))

    return {
        "status": "received",
        "log_id": str(face_log.id),
        "face_id": payload.face_id,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# FACE LOGS
# ═══════════════════════════════════════════════════════════════════════════════
@router.get(
    "/logs",
    response_model=PaginatedResponse[FaceLogResponse],
    summary="Face ID loglar ro'yxati",
)
async def list_face_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
    device_id: Optional[uuid.UUID] = None,
    is_processed: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(FaceLog)
    if device_id:
        query = query.where(FaceLog.device_id == device_id)
    if is_processed is not None:
        query = query.where(FaceLog.is_processed == is_processed)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    logs = (await db.execute(
        query.offset(skip).limit(limit).order_by(FaceLog.received_at.desc())
    )).scalars().all()
    return PaginatedResponse.create(data=logs, total=total, skip=skip, limit=limit)

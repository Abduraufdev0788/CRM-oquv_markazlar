"""
Face ID IoT webhook — /api/v1/face/
"""
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.iot import FaceDevice, FaceLog
from app.core.security import hash_token
from app.tasks.notification_tasks import process_face_log

router = APIRouter(prefix="/face", tags=["IoT / Face ID"])


@router.post("/webhook", summary="Face ID qurilmadan log qabul qilish")
async def face_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_device_secret: str = Header(..., description="Qurilma API secret"),
):
    """
    Face ID qurilma har safar yuz taniganda shu endpointga POST yuboradi.
    1. Qurilmani api_secret orqali autentifikatsiya qilamiz.
    2. FaceLog ga xom ma'lumotni saqlaymiz.
    3. Celery task orqali asinxron tahlil qilamiz.
    """
    payload = await request.json()

    # Qurilmani tekshirish
    secret_hash = hash_token(x_device_secret)
    result = await db.execute(
        select(FaceDevice).where(FaceDevice.api_secret == x_device_secret)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=401, detail="Noto'g'ri qurilma yoki secret")

    # Xom logni saqlash
    face_log = FaceLog(
        device_id=device.id,
        face_data_id=payload.get("face_id", ""),
        raw_payload=payload,
        logged_at=datetime.fromisoformat(payload.get("timestamp", datetime.now(timezone.utc).isoformat())),
        received_at=datetime.now(timezone.utc),
    )
    db.add(face_log)
    await db.flush()

    # Asinxron tahlil (Celery)
    process_face_log.delay(str(face_log.id))

    return {"status": "received", "log_id": str(face_log.id)}


@router.get("/devices", summary="Face ID qurilmalar ro'yxati")
async def list_devices(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(FaceDevice).order_by(FaceDevice.created_at.desc()))
    return result.scalars().all()

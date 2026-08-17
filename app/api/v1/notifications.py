from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, func
from datetime import datetime

from app.database import get_db
from app.models.user import User, UserRole
from app.models.system import Notification, NotificationChannel
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/")
async def get_my_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Joriy foydalanuvchining (Admin/Ustoz) tizim ichidagi xabarlarini qaytaradi."""
    query = (
        select(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.channel == NotificationChannel.IN_APP
        )
        .order_by(Notification.created_at.desc())
        .limit(20)
    )
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return [
        {
            "id": str(n.id),
            "title": n.title,
            "body": n.body,
            "is_read": n.is_read,
            "type": n.notif_type.value,
            "created_at": n.created_at
        }
        for n in notifications
    ]


@router.put("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Bitta xabarni o'qilgan deb belgilash."""
    query = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    )
    notif = (await db.execute(query)).scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Xabar topilmadi")
    
    notif.is_read = True
    await db.commit()
    return {"success": True}


@router.put("/read-all")
async def mark_all_as_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Barcha o'qilmagan xabarlarni o'qilgan deb belgilash."""
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
            Notification.channel == NotificationChannel.IN_APP
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"success": True}

from app.schemas.system import NotificationSendRequest
from app.models.system import NotificationType, NotificationStatus
from app.models.student import Student
from app.models.academic import Enrollment, EnrollmentStatus

@router.post("/send", summary="Admin tomonidan ixtiyoriy xabar yuborish")
async def send_notification(
    data: NotificationSendRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Admin ixtiyoriy matn yozib hohlagan kishisiga xabar jo'natadi."""
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    notifications = []
    
    if data.target == "teachers":
        users = (await db.execute(select(User).where(User.role == UserRole.TEACHER))).scalars().all()
        for u in users:
            notifications.append(Notification(user_id=u.id, title=data.title, body=data.body, notif_type=NotificationType.GENERAL, channel=data.channel, status=NotificationStatus.SENT))
            
    elif data.target == "students":
        students = (await db.execute(select(Student))).scalars().all()
        for s in students:
            notifications.append(Notification(student_id=s.id, title=data.title, body=data.body, notif_type=NotificationType.GENERAL, channel=data.channel, status=NotificationStatus.SENT))
            
    elif data.target == "group" and data.group_id:
        enrolls = (await db.execute(select(Enrollment).where(Enrollment.group_id == data.group_id, Enrollment.status == EnrollmentStatus.ACTIVE))).scalars().all()
        for e in enrolls:
            notifications.append(Notification(student_id=e.student_id, title=data.title, body=data.body, notif_type=NotificationType.GENERAL, channel=data.channel, status=NotificationStatus.SENT))
            
    elif data.target == "all":
        users = (await db.execute(select(User))).scalars().all()
        for u in users:
            notifications.append(Notification(user_id=u.id, title=data.title, body=data.body, notif_type=NotificationType.GENERAL, channel=data.channel, status=NotificationStatus.SENT))
        students = (await db.execute(select(Student))).scalars().all()
        for s in students:
            notifications.append(Notification(student_id=s.id, title=data.title, body=data.body, notif_type=NotificationType.GENERAL, channel=data.channel, status=NotificationStatus.SENT))
    
    else:
        raise HTTPException(status_code=400, detail="Noto'g'ri nishon (target) tanlandi")

    if notifications:
        db.add_all(notifications)
        await db.commit()
        
    return {"success": True, "count": len(notifications)}


@router.get("/history", summary="Yuborilgan xabarlar tarixi")
async def get_notification_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
        
    # Tarixni NotificationType.GENERAL va qo'lda kiritilganlarini qaytaramiz.
    query = (
        select(Notification.title, Notification.body, Notification.created_at, Notification.channel, func.count(Notification.id).label('sent_count'))
        .where(Notification.notif_type == NotificationType.GENERAL)
        .group_by(Notification.title, Notification.body, Notification.created_at, Notification.channel)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    result = (await db.execute(query)).all()
    
    return [
        {
            "title": r[0],
            "body": r[1],
            "created_at": r[2],
            "channel": r[3].value if r[3] else None,
            "count": r[4]
        }
        for r in result
    ]

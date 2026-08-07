import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import AuditLog, AuditAction


async def write_audit_log(
    db: AsyncSession,
    *,
    action: AuditAction,
    table_name: str,
    user_id: Optional[uuid.UUID] = None,
    record_id: Optional[uuid.UUID] = None,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    description: Optional[str] = None,
) -> AuditLog:
    """
    Har qanday muhim amal uchun audit log yozish yordamchisi.
    AuditLog jadvaliga faqat INSERT — UPDATE/DELETE ta'qiqlangan.
    """
    log = AuditLog(
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
        user_agent=user_agent,
        description=description,
    )
    db.add(log)
    # Commit chaqirilmaydi — caller tomonidan commit bo'ladi
    return log

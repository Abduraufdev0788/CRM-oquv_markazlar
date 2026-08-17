import enum
from typing import Optional
from sqlalchemy import String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    TRIAL = "trial"
    ENROLLED = "enrolled"
    REJECTED = "rejected"


class Lead(BaseModel):
    __tablename__ = "leads"

    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True) # e.g. Instagram, Telegram, Flayer
    status: Mapped[LeadStatus] = mapped_column(
        SAEnum(LeadStatus, name="leadstatus"), nullable=False, default=LeadStatus.NEW, index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    def __repr__(self):
        return f"<Lead {self.first_name} {self.phone} - {self.status.value}>"

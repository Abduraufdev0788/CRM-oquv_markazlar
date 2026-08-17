from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.lead import LeadStatus


class LeadBase(BaseModel):
    first_name: str = Field(..., max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    phone: str = Field(..., max_length=20)
    source: Optional[str] = Field(None, max_length=50)
    status: LeadStatus = LeadStatus.NEW
    notes: Optional[str] = None


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    source: Optional[str] = Field(None, max_length=50)
    status: Optional[LeadStatus] = None
    notes: Optional[str] = None


class LeadResponse(LeadBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

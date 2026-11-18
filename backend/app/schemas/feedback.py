from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    category: str = Field("GENERAL", description="ELECTRIC_WATER, SECURITY, HYGIENE, GENERAL")
    title: str = Field(..., min_length=2, max_length=255)
    content: str = Field(..., min_length=2)


class FeedbackReplyRequest(BaseModel):
    admin_reply: str = Field(..., min_length=1)


class FeedbackResponse(BaseModel):
    id: int
    room_id: int
    room_number: Optional[str] = None
    floor: Optional[int] = None
    tenant_id: int
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    category: str
    title: str
    content: str
    status: str  # UNREAD, READ, RESOLVED
    is_read_by_admin: bool
    is_reply_read_by_tenant: bool = True
    admin_reply: Optional[str] = None
    replied_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

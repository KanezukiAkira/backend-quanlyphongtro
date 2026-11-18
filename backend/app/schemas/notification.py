from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: int
    recipient_role: str
    recipient_user_id: Optional[int] = None
    room_id: Optional[int] = None
    room_number: Optional[str] = None
    title: str
    message: str
    type: str
    related_id: Optional[int] = None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

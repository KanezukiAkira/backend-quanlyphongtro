from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TenantResponse(BaseModel):
    id: int
    username: str
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    role: str = "TENANT"
    created_at: Optional[datetime] = None
    current_room_id: Optional[int] = None
    current_room_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

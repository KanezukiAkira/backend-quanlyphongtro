from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TenantResponse(BaseModel):
    id: int
    username: str
    full_name: str
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    cccd: Optional[str] = None
    hometown: Optional[str] = None
    role: str = "TENANT"
    room_id: Optional[int] = None
    is_profile_completed: bool = False
    token_version: int = 1
    created_at: Optional[datetime] = None
    current_room_id: Optional[int] = None
    current_room_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ArchivedTenantResponse(BaseModel):
    id: int
    original_user_id: Optional[int] = None
    room_id: Optional[int] = None
    room_number: str
    username: Optional[str] = None
    full_name: str
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    cccd: Optional[str] = None
    hometown: Optional[str] = None
    contract_code: Optional[str] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    checkout_reason: Optional[str] = None
    status: str = "ARCHIVED"
    deleted_at: datetime
    expire_at: datetime
    days_remaining: int = 30

    model_config = ConfigDict(from_attributes=True)

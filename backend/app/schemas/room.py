from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class RoomBase(BaseModel):
    room_number: Optional[str] = Field(None, min_length=1, max_length=50)
    floor: int = Field(1, ge=1)
    room_seq: int = Field(1, ge=1)
    price: float = Field(2000000.0, ge=0.0)
    area: Optional[float] = Field(22.0, ge=0.0)
    max_occupants: int = Field(2, ge=1)
    status: str = Field("AVAILABLE", max_length=50)  # AVAILABLE, RENTED, MAINTENANCE
    electricity_rate: float = Field(3500.0, ge=0.0)
    water_rate: float = Field(20000.0, ge=0.0)
    parking_fee: float = Field(100000.0, ge=0.0)
    trash_fee: float = Field(30000.0, ge=0.0)
    wifi_fee: float = Field(50000.0, ge=0.0)
    maintenance_fee: float = Field(20000.0, ge=0.0)
    description: Optional[str] = None


class RoomCreate(RoomBase):
    default_password: Optional[str] = Field("123456", min_length=4, max_length=100)


class FloorCreateRequest(BaseModel):
    floor: int = Field(..., ge=1, le=50)
    num_rooms: int = Field(5, ge=1, le=20)
    base_price: float = Field(2000000.0, ge=0.0)
    area: float = Field(22.0, ge=0.0)
    default_password: str = Field("123456", min_length=4, max_length=100)


class RoomCheckoutRequest(BaseModel):
    new_password: Optional[str] = Field("123456", min_length=4, max_length=100)
    checkout_reason: Optional[str] = Field("Khách thuê kết thúc hợp đồng và trả phòng", max_length=500)


class RoomUpdate(BaseModel):
    room_number: Optional[str] = Field(None, min_length=1, max_length=50)
    floor: Optional[int] = Field(None, ge=1)
    room_seq: Optional[int] = Field(None, ge=1)
    price: Optional[float] = Field(None, ge=0.0)
    area: Optional[float] = Field(None, ge=0.0)
    max_occupants: Optional[int] = Field(None, ge=1)
    status: Optional[str] = Field(None, max_length=50)
    electricity_rate: Optional[float] = Field(None, ge=0.0)
    water_rate: Optional[float] = Field(None, ge=0.0)
    parking_fee: Optional[float] = Field(None, ge=0.0)
    trash_fee: Optional[float] = Field(None, ge=0.0)
    wifi_fee: Optional[float] = Field(None, ge=0.0)
    maintenance_fee: Optional[float] = Field(None, ge=0.0)
    description: Optional[str] = None


class RoomResponse(BaseModel):
    id: int
    room_number: str
    floor: int = 1
    room_seq: int = 1
    price: float
    area: Optional[float] = None
    max_occupants: int
    status: str
    electricity_rate: float = 3500.0
    water_rate: float = 20000.0
    parking_fee: float = 100000.0
    trash_fee: float = 30000.0
    wifi_fee: float = 50000.0
    maintenance_fee: float = 20000.0
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    # Enriched info for Admin UI
    account_username: Optional[str] = None
    tenant_id: Optional[int] = None
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_email: Optional[str] = None
    tenant_cccd: Optional[str] = None
    tenant_gender: Optional[str] = None
    tenant_birth_date: Optional[str] = None
    tenant_hometown: Optional[str] = None
    is_profile_completed: Optional[bool] = False
    has_overdue_invoice: Optional[bool] = False
    overdue_amount: Optional[float] = 0.0
    overdue_months_count: Optional[int] = 0
    pending_bill_count: Optional[int] = 0
    active_contract_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

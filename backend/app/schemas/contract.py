from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.room import RoomResponse
from app.schemas.tenant import TenantResponse


class ContractBase(BaseModel):
    room_id: int
    tenant_id: Optional[int] = None
    start_date: date
    end_date: date
    deposit_amount: float = Field(2000000.0, ge=0.0)
    monthly_rent: Optional[float] = Field(None, ge=0.0)
    electricity_rate: float = Field(3500.0, ge=0.0)
    water_rate: float = Field(20000.0, ge=0.0)
    parking_fee: float = Field(100000.0, ge=0.0)
    trash_fee: float = Field(30000.0, ge=0.0)
    wifi_fee: float = Field(50000.0, ge=0.0)
    maintenance_fee: float = Field(20000.0, ge=0.0)
    service_fee: Optional[float] = Field(None, ge=0.0)
    payment_due_day: int = Field(10, ge=1, le=28)
    landlord_name: Optional[str] = "Nguyễn Minh Hoàng"
    landlord_cccd: Optional[str] = "079085001234"
    landlord_phone: Optional[str] = "0901234567"
    landlord_address: Optional[str] = "Số 128 Nguyễn Văn Cừ, Phường 4, Quận 5, TP. Hồ Chí Minh"
    notes: Optional[str] = None


class ContractCreate(ContractBase):
    pass


class ContractUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    deposit_amount: Optional[float] = Field(None, ge=0.0)
    monthly_rent: Optional[float] = Field(None, ge=0.0)
    electricity_rate: Optional[float] = Field(None, ge=0.0)
    water_rate: Optional[float] = Field(None, ge=0.0)
    parking_fee: Optional[float] = Field(None, ge=0.0)
    trash_fee: Optional[float] = Field(None, ge=0.0)
    wifi_fee: Optional[float] = Field(None, ge=0.0)
    maintenance_fee: Optional[float] = Field(None, ge=0.0)
    service_fee: Optional[float] = Field(None, ge=0.0)
    status: Optional[str] = None
    notes: Optional[str] = None


class ContractResponse(BaseModel):
    id: int
    contract_code: str
    room_id: int
    tenant_id: int
    start_date: date
    end_date: date
    deposit_amount: float
    monthly_rent: float
    electricity_rate: float
    water_rate: float
    parking_fee: float = 100000.0
    trash_fee: float = 30000.0
    wifi_fee: float = 50000.0
    maintenance_fee: float = 20000.0
    service_fee: float
    payment_due_day: int = 10
    landlord_name: Optional[str] = "Nguyễn Minh Hoàng"
    landlord_cccd: Optional[str] = "079085001234"
    landlord_phone: Optional[str] = "0901234567"
    landlord_address: Optional[str] = "Số 128 Nguyễn Văn Cừ, Phường 4, Quận 5, TP. Hồ Chí Minh"
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    # Optional nested details
    room: Optional[RoomResponse] = None
    tenant: Optional[TenantResponse] = None

    model_config = ConfigDict(from_attributes=True)

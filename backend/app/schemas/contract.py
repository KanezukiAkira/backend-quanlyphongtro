from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.room import RoomResponse
from app.schemas.tenant import TenantResponse


class ContractBase(BaseModel):
    room_id: int
    tenant_id: int
    start_date: date
    end_date: date
    deposit_amount: float = Field(0.0, ge=0.0)
    monthly_rent: Optional[float] = Field(None, ge=0.0)
    electricity_rate: float = Field(3500.0, ge=0.0)
    water_rate: float = Field(20000.0, ge=0.0)
    service_fee: float = Field(50000.0, ge=0.0)
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
    service_fee: float
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    # Optional nested details
    room: Optional[RoomResponse] = None
    tenant: Optional[TenantResponse] = None

    model_config = ConfigDict(from_attributes=True)

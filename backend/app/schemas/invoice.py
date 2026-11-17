from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.room import RoomResponse
from app.schemas.tenant import TenantResponse


class InvoiceGenerateMonthly(BaseModel):
    month_year: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="Format: YYYY-MM")
    issue_date: Optional[date] = None
    due_date: Optional[date] = None


class InvoiceCreateManual(BaseModel):
    room_id: int
    contract_id: Optional[int] = None
    tenant_id: int
    month_year: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    room_charge: float = Field(0.0, ge=0.0)
    electricity_usage: float = Field(0.0, ge=0.0)
    electricity_rate: float = Field(0.0, ge=0.0)
    electricity_charge: float = Field(0.0, ge=0.0)
    water_usage: float = Field(0.0, ge=0.0)
    water_rate: float = Field(0.0, ge=0.0)
    water_charge: float = Field(0.0, ge=0.0)
    service_charge: float = Field(0.0, ge=0.0)
    other_charge: float = Field(0.0, ge=0.0)
    discount: float = Field(0.0, ge=0.0)
    notes: Optional[str] = None


class InvoicePayRequest(BaseModel):
    payment_method: str = Field("CASH", description="Payment method, e.g. CASH, BANK_TRANSFER")
    notes: Optional[str] = None


class InvoiceResponse(BaseModel):
    id: int
    invoice_code: str
    room_id: int
    contract_id: Optional[int] = None
    tenant_id: int
    month_year: str
    issue_date: date
    due_date: date
    room_charge: float
    electricity_usage: float
    electricity_rate: float
    electricity_charge: float
    water_usage: float
    water_rate: float
    water_charge: float
    service_charge: float
    other_charge: float
    discount: float
    total_amount: float
    status: str  # UNPAID, PAID, OVERDUE
    paid_date: Optional[date] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    # Nested or helper fields
    room: Optional[RoomResponse] = None
    tenant: Optional[TenantResponse] = None

    model_config = ConfigDict(from_attributes=True)

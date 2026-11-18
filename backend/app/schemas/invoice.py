from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.room import RoomResponse
from app.schemas.tenant import TenantResponse


class InvoiceGenerateMonthly(BaseModel):
    month_year: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="Format: YYYY-MM")
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    send_email: bool = True


class InvoiceCreateManual(BaseModel):
    room_id: int
    contract_id: Optional[int] = None
    tenant_id: Optional[int] = None
    month_year: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    room_charge: float = Field(2000000.0, ge=0.0)
    old_electricity: float = Field(0.0, ge=0.0)
    new_electricity: float = Field(0.0, ge=0.0)
    electricity_usage: float = Field(0.0, ge=0.0)
    electricity_rate: float = Field(3500.0, ge=0.0)
    electricity_charge: float = Field(0.0, ge=0.0)
    old_water: float = Field(0.0, ge=0.0)
    new_water: float = Field(0.0, ge=0.0)
    water_usage: float = Field(0.0, ge=0.0)
    water_rate: float = Field(20000.0, ge=0.0)
    water_charge: float = Field(0.0, ge=0.0)
    parking_fee: float = Field(100000.0, ge=0.0)
    trash_fee: float = Field(30000.0, ge=0.0)
    wifi_fee: float = Field(50000.0, ge=0.0)
    maintenance_fee: float = Field(20000.0, ge=0.0)
    service_charge: float = Field(200000.0, ge=0.0)
    other_charge: float = Field(0.0, ge=0.0)
    discount: float = Field(0.0, ge=0.0)
    notes: Optional[str] = None
    send_email: bool = True


class InvoicePayRequest(BaseModel):
    payment_method: str = Field("MOMO", description="MOMO, VISA, LINKED_BANK, BANK_TRANSFER, CASH")
    transaction_ref: Optional[str] = None
    notes: Optional[str] = None


class InvoiceUploadBillRequest(BaseModel):
    bill_image_url: str = Field(..., description="Data URL hoặc đường dẫn ảnh chụp màn hình UNC chuyển khoản")
    notes: Optional[str] = None


class InvoiceApproveBillRequest(BaseModel):
    is_reconciled: bool = True
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
    overdue_date: Optional[date] = None

    room_charge: float
    old_electricity: float = 0.0
    new_electricity: float = 0.0
    electricity_usage: float
    electricity_rate: float
    electricity_charge: float

    old_water: float = 0.0
    new_water: float = 0.0
    water_usage: float
    water_rate: float
    water_charge: float

    parking_fee: float = 100000.0
    trash_fee: float = 30000.0
    wifi_fee: float = 50000.0
    maintenance_fee: float = 20000.0
    service_charge: float

    other_charge: float
    discount: float
    total_amount: float
    status: str  # UNPAID, PENDING_APPROVAL, PAID, OVERDUE
    paid_date: Optional[date] = None
    paid_at: Optional[datetime] = None
    payment_method: Optional[str] = None
    transaction_ref: Optional[str] = None
    bill_image_url: Optional[str] = None
    bill_uploaded_at: Optional[datetime] = None
    is_reconciled: bool = False
    email_sent: bool = False
    email_sent_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    # Nested or helper fields
    room: Optional[RoomResponse] = None
    tenant: Optional[TenantResponse] = None

    model_config = ConfigDict(from_attributes=True)

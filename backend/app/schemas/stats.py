from datetime import date
from typing import List, Optional
from pydantic import BaseModel


class DashboardStatsResponse(BaseModel):
    total_rooms: int
    available_rooms: int
    rented_rooms: int
    maintenance_rooms: int
    total_tenants: int
    active_contracts: int
    unpaid_invoices_count: int
    paid_invoices_count: int
    overdue_invoices_count: int
    monthly_expected_revenue: float
    monthly_actual_revenue: float
    total_unpaid_amount: float


class MonthlyRevenueItem(BaseModel):
    month_year: str
    expected_amount: float
    collected_amount: float
    unpaid_amount: float


class RevenueStatsResponse(BaseModel):
    total_collected_revenue: float
    total_unpaid_revenue: float
    monthly_breakdown: List[MonthlyRevenueItem]


class OverdueInvoiceItem(BaseModel):
    id: int
    invoice_code: str
    room_id: int
    room_number: Optional[str] = None
    tenant_id: int
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    month_year: str
    total_amount: float
    due_date: date
    days_overdue: int

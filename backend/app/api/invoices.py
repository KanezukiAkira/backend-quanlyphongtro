from datetime import date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_landlord
from app.models.invoice import Invoice
from app.models.room import Room
from app.models.user import User
from app.schemas.invoice import (
    InvoiceGenerateMonthly,
    InvoiceCreateManual,
    InvoicePayRequest,
    InvoiceResponse,
)
from app.services.billing_service import (
    generate_monthly_invoices,
    pay_invoice,
    get_invoices,
    get_tenant_invoices,
    get_invoice_by_id,
)

router = APIRouter()


@router.post("/generate-monthly", response_model=List[InvoiceResponse])
def generate_monthly(
    gen_in: InvoiceGenerateMonthly,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Tự động lập hóa đơn tiền phòng & điện nước hàng tháng cho tất cả phòng đang có hợp đồng hiệu lực (chỉ chủ trọ).
    Công thức: Tổng = Tiền phòng + Tiền điện (chỉ số * đơn giá) + Tiền nước (chỉ số * đơn giá) + Phí dịch vụ.
    Trạng thái ban đầu: UNPAID.
    """
    return generate_monthly_invoices(
        db,
        month_year=gen_in.month_year,
        issue_date=gen_in.issue_date,
        due_date=gen_in.due_date,
    )


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_invoice(
    inv_in: InvoiceCreateManual,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Tạo hóa đơn thủ công (chỉ chủ trọ)."""
    room = db.query(Room).filter(Room.id == inv_in.room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phòng có ID {inv_in.room_id}",
        )

    tenant = db.query(User).filter(User.id == inv_in.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách thuê có ID {inv_in.tenant_id}",
        )

    clean_month = inv_in.month_year.replace("-", "")
    code_prefix = f"INV-{room.room_number}-{clean_month}"
    conflict = db.query(Invoice).filter(Invoice.invoice_code == code_prefix).first()
    invoice_code = f"{code_prefix}-{int(date.today().strftime('%Y%m%d%H%M%S'))}" if conflict else code_prefix

    actual_issue_date = inv_in.issue_date or date.today()
    actual_due_date = inv_in.due_date or (actual_issue_date + timedelta(days=10))

    total_amount = round(
        inv_in.room_charge
        + inv_in.electricity_charge
        + inv_in.water_charge
        + inv_in.service_charge
        + inv_in.other_charge
        - inv_in.discount,
        2,
    )

    invoice = Invoice(
        invoice_code=invoice_code,
        room_id=inv_in.room_id,
        contract_id=inv_in.contract_id,
        tenant_id=inv_in.tenant_id,
        month_year=inv_in.month_year,
        issue_date=actual_issue_date,
        due_date=actual_due_date,
        room_charge=inv_in.room_charge,
        electricity_usage=inv_in.electricity_usage,
        electricity_rate=inv_in.electricity_rate,
        electricity_charge=inv_in.electricity_charge,
        water_usage=inv_in.water_usage,
        water_rate=inv_in.water_rate,
        water_charge=inv_in.water_charge,
        service_charge=inv_in.service_charge,
        other_charge=inv_in.other_charge,
        discount=inv_in.discount,
        total_amount=total_amount,
        status="UNPAID",
        notes=inv_in.notes,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("", response_model=List[InvoiceResponse])
@router.get("/", response_model=List[InvoiceResponse], include_in_schema=False)
def list_invoices(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: UNPAID, PAID, OVERDUE"),
    month_year: Optional[str] = Query(None, description="Lọc theo tháng (YYYY-MM)"),
    room_id: Optional[int] = Query(None, description="Lọc theo ID phòng"),
    tenant_id: Optional[int] = Query(None, description="Lọc theo ID khách thuê"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Lấy danh sách tất cả hóa đơn (chỉ chủ trọ)."""
    return get_invoices(
        db,
        status=status,
        month_year=month_year,
        room_id=room_id,
        tenant_id=tenant_id,
        skip=skip,
        limit=limit,
    )


@router.get("/my-invoices", response_model=List[InvoiceResponse])
def get_my_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách các hóa đơn của khách thuê đang đăng nhập."""
    return get_tenant_invoices(db, tenant_id=current_user.id)


@router.get("/{id}", response_model=InvoiceResponse)
def get_invoice(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xem chi tiết hóa đơn theo ID."""
    invoice = get_invoice_by_id(db, id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hóa đơn có ID {id}",
        )
    if current_user.role == "TENANT" and invoice.tenant_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem thông tin hóa đơn này",
        )
    return invoice


@router.post("/{id}/pay", response_model=InvoiceResponse)
def pay_invoice_endpoint(
    id: int,
    pay_in: Optional[InvoicePayRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Thanh toán toàn bộ hóa đơn.
    Quy tắc: Thanh toán 100% đầy đủ, ngay lập tức chuyển trạng thái sang 'PAID' (không hỗ trợ thanh toán từng phần).
    """
    payment_method = pay_in.payment_method if pay_in else "CASH"
    notes = pay_in.notes if pay_in else None
    return pay_invoice(
        db,
        invoice_id=id,
        payment_method=payment_method,
        notes=notes,
    )

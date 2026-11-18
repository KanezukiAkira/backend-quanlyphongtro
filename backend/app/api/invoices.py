from datetime import date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_landlord
from app.models.email_log import EmailLog
from app.models.invoice import Invoice
from app.models.room import Room
from app.models.user import User
from app.schemas.invoice import (
    InvoiceApproveBillRequest,
    InvoiceCreateManual,
    InvoiceGenerateMonthly,
    InvoicePayRequest,
    InvoiceResponse,
    InvoiceUploadBillRequest,
)
from app.services.billing_service import (
    approve_invoice_bill,
    generate_monthly_invoices,
    get_invoice_by_id,
    get_invoices,
    get_tenant_invoices,
    pay_invoice,
    reconcile_demo_transaction,
    upload_invoice_bill,
)
from app.services.notification_service import create_notification
from app.services.pdf_email_service import generate_invoice_pdf, send_invoice_email

router = APIRouter()


@router.post("/generate-monthly", response_model=List[InvoiceResponse])
def generate_monthly(
    gen_in: InvoiceGenerateMonthly,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Tự động lập hóa đơn tiền phòng & điện nước hàng tháng cho tất cả phòng đang có hợp đồng hiệu lực (chỉ chủ trọ).
    Tự động gửi thông báo & Gmail hóa đơn cho đúng từng phòng.
    """
    return generate_monthly_invoices(
        db,
        month_year=gen_in.month_year,
        issue_date=gen_in.issue_date,
        due_date=gen_in.due_date,
        send_email=gen_in.send_email,
    )


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_invoice(
    inv_in: InvoiceCreateManual,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Tạo hóa đơn thủ công cho một phòng (chỉ chủ trọ)."""
    room = db.query(Room).filter(Room.id == inv_in.room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phòng có ID {inv_in.room_id}",
        )

    tenant = None
    if inv_in.tenant_id:
        tenant = db.query(User).filter(User.id == inv_in.tenant_id).first()
    else:
        tenant = (
            db.query(User)
            .filter((User.room_id == room.id) | (User.username == room.room_number))
            .first()
        )
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách thuê của phòng này",
        )

    clean_month = inv_in.month_year.replace("-", "")
    code_prefix = f"INV-{room.room_number}-{clean_month}"
    conflict = db.query(Invoice).filter(Invoice.invoice_code == code_prefix).first()
    invoice_code = f"{code_prefix}-{int(date.today().strftime('%Y%m%d%H%M%S'))}" if conflict else code_prefix

    actual_issue_date = inv_in.issue_date or date.today()
    if inv_in.due_date:
        actual_due_date = inv_in.due_date
    else:
        try:
            y_str, m_str = inv_in.month_year.split("-")
            actual_due_date = date(int(y_str), int(m_str), 10)
        except Exception:
            actual_due_date = actual_issue_date + timedelta(days=10)

    overdue_date = actual_due_date + timedelta(days=5)

    elec_usage = inv_in.electricity_usage or max(0.0, inv_in.new_electricity - inv_in.old_electricity)
    elec_charge = inv_in.electricity_charge or round(elec_usage * inv_in.electricity_rate, 2)

    water_usage = inv_in.water_usage or max(0.0, inv_in.new_water - inv_in.old_water)
    water_charge = inv_in.water_charge or round(water_usage * inv_in.water_rate, 2)

    service_charge = inv_in.service_charge or (
        inv_in.parking_fee + inv_in.trash_fee + inv_in.wifi_fee + inv_in.maintenance_fee
    )

    total_amount = round(
        inv_in.room_charge
        + elec_charge
        + water_charge
        + service_charge
        + inv_in.other_charge
        - inv_in.discount,
        2,
    )

    invoice = Invoice(
        invoice_code=invoice_code,
        room_id=inv_in.room_id,
        contract_id=inv_in.contract_id,
        tenant_id=tenant.id,
        month_year=inv_in.month_year,
        issue_date=actual_issue_date,
        due_date=actual_due_date,
        overdue_date=overdue_date,
        room_charge=inv_in.room_charge,
        old_electricity=inv_in.old_electricity,
        new_electricity=inv_in.new_electricity,
        electricity_usage=elec_usage,
        electricity_rate=inv_in.electricity_rate,
        electricity_charge=elec_charge,
        old_water=inv_in.old_water,
        new_water=inv_in.new_water,
        water_usage=water_usage,
        water_rate=inv_in.water_rate,
        water_charge=water_charge,
        parking_fee=inv_in.parking_fee,
        trash_fee=inv_in.trash_fee,
        wifi_fee=inv_in.wifi_fee,
        maintenance_fee=inv_in.maintenance_fee,
        service_charge=service_charge,
        other_charge=inv_in.other_charge,
        discount=inv_in.discount,
        total_amount=total_amount,
        status="UNPAID",
        notes=inv_in.notes,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    create_notification(
        db,
        recipient_role="TENANT",
        recipient_user_id=tenant.id,
        room_id=room.id,
        title=f"Hóa đơn mới kỳ {invoice.month_year} - Phòng {room.room_number}",
        message=f"Hóa đơn {invoice.invoice_code} với tổng tiền {invoice.total_amount:,.0f}đ đã được phát hành. Hạn đóng: {invoice.due_date.strftime('%d/%m/%Y')}.",
        notif_type="INVOICE_CREATED",
        related_id=invoice.id,
    )

    if inv_in.send_email:
        try:
            send_invoice_email(db, invoice, email_type="INVOICE_ISSUED")
        except Exception:
            pass

    return invoice


@router.get("", response_model=List[InvoiceResponse])
@router.get("/", response_model=List[InvoiceResponse], include_in_schema=False)
def list_invoices(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: UNPAID, PENDING_APPROVAL, PAID, OVERDUE"),
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
    """Lấy danh sách các hóa đơn của khách thuê / tài khoản phòng đang đăng nhập (cô lập dữ liệu)."""
    return get_tenant_invoices(db, tenant_id=current_user.id, room_id=current_user.room_id)


@router.get("/email-logs")
def list_email_logs(
    room_id: Optional[int] = Query(None),
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xem lịch sử gửi Hóa đơn & Biên lai PDF qua Gmail."""
    query = db.query(EmailLog)
    if current_user.role != "LANDLORD":
        query = query.filter(EmailLog.room_id == current_user.room_id)
    elif room_id:
        query = query.filter(EmailLog.room_id == room_id)
    logs = query.order_by(EmailLog.created_at.desc(), EmailLog.id.desc()).limit(limit).all()
    return [
        {
            "id": lg.id,
            "room_id": lg.room_id,
            "invoice_id": lg.invoice_id,
            "recipient_email": lg.recipient_email,
            "recipient_name": lg.recipient_name,
            "subject": lg.subject,
            "body_html": lg.body_html,
            "attachment_name": lg.attachment_name,
            "status": lg.status,
            "created_at": lg.created_at,
        }
        for lg in logs
    ]


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
    if current_user.role == "TENANT":
        if invoice.tenant_id != current_user.id and invoice.room_id != current_user.room_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xem thông tin hóa đơn của phòng khác",
            )
    return invoice


@router.get("/{id}/pdf")
def download_invoice_pdf(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Xuất / Tải xuống Hóa đơn tiền trọ chuẩn Việt Nam (File PDF).
    """
    invoice = get_invoice_by_id(db, id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hóa đơn",
        )
    if current_user.role == "TENANT":
        if invoice.tenant_id != current_user.id and invoice.room_id != current_user.room_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền tải hóa đơn của phòng khác",
            )
    pdf_bytes = generate_invoice_pdf(invoice)
    filename = f"Hoa-Don-Phong-Tro-{invoice.invoice_code}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{id}/send-email")
def send_invoice_email_endpoint(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Gửi Hóa đơn / Biên lai PDF vào Gmail của phòng."""
    invoice = get_invoice_by_id(db, id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hóa đơn",
        )
    if current_user.role == "TENANT":
        if invoice.tenant_id != current_user.id and invoice.room_id != current_user.room_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền thao tác trên hóa đơn của phòng khác",
            )
    e_type = "PAYMENT_RECEIPT" if invoice.status == "PAID" else (
        "OVERDUE_REMINDER" if invoice.status == "OVERDUE" else "INVOICE_ISSUED"
    )
    log_entry = send_invoice_email(db, invoice, email_type=e_type)
    return {
        "message": f"Đã gửi Hóa đơn PDF ({log_entry.attachment_name}) tới Gmail: {log_entry.recipient_email}",
        "recipient_email": log_entry.recipient_email,
        "subject": log_entry.subject,
        "attachment_name": log_entry.attachment_name,
        "status": log_entry.status,
    }


@router.post("/{id}/pay", response_model=InvoiceResponse)
def pay_invoice_endpoint(
    id: int,
    pay_in: Optional[InvoicePayRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Phương thức 1 - Cổng Thanh toán Online (Momo, Thẻ Visa, Ngân hàng liên kết):
    Xác nhận thanh toán -> Xử lý thành công ngay lập tức -> Gạch nợ (PAID) -> Gửi thông báo cho Chủ trọ & gửi PDF vào Gmail khách thuê.
    """
    invoice = get_invoice_by_id(db, id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn")
    if current_user.role == "TENANT":
        if invoice.tenant_id != current_user.id and invoice.room_id != current_user.room_id:
            raise HTTPException(status_code=403, detail="Không có quyền thanh toán hóa đơn phòng khác")

    payment_method = pay_in.payment_method if pay_in else "MOMO"
    tx_ref = pay_in.transaction_ref if pay_in else None
    notes = pay_in.notes if pay_in else None
    return pay_invoice(
        db,
        invoice_id=id,
        payment_method=payment_method,
        transaction_ref=tx_ref,
        notes=notes,
    )


@router.post("/{id}/upload-bill", response_model=InvoiceResponse)
def upload_bill_endpoint(
    id: int,
    bill_in: InvoiceUploadBillRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Phương thức 2 - Chuyển khoản Ngân hàng (VietQR) & Tải ảnh chụp màn hình Bill (UNC) lên hệ thống.
    Chuyển trạng thái sang 'PENDING_APPROVAL' (Chờ chủ trọ duyệt bill).
    """
    invoice = get_invoice_by_id(db, id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn")
    if current_user.role == "TENANT":
        if invoice.tenant_id != current_user.id and invoice.room_id != current_user.room_id:
            raise HTTPException(status_code=403, detail="Không có quyền tải bill cho phòng khác")

    return upload_invoice_bill(
        db,
        invoice_id=id,
        bill_image_url=bill_in.bill_image_url,
        notes=bill_in.notes,
    )


@router.post("/{id}/reconcile")
def reconcile_bill_endpoint(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Chủ trọ bấm 'Kiểm tra / Đối soát giao dịch Demo' xác nhận tiền chuyển khoản đã vào TK Ngân hàng.
    """
    return reconcile_demo_transaction(db, invoice_id=id)


@router.post("/{id}/approve-bill", response_model=InvoiceResponse)
def approve_bill_endpoint(
    id: int,
    req: Optional[InvoiceApproveBillRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Chủ trọ bấm 'Xác nhận đã thu tiền' sau khi kiểm tra Bill chuyển khoản:
    Đánh dấu Đã đóng tiền (PAID) và tự động gửi biên lai PDF qua Gmail của phòng đó.
    """
    notes = req.notes if req else None
    return approve_invoice_bill(db, invoice_id=id, notes=notes)

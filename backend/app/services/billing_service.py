from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.contract import Contract
from app.models.invoice import Invoice
from app.models.room import Room
from app.models.utility_reading import UtilityReading
from app.services.notification_service import create_notification
from app.services.pdf_email_service import send_invoice_email


def check_and_update_overdue_invoices(db: Session) -> int:
    """
    Hạn đóng tiền cố định: Ngày 10 hằng tháng (due_date).
    Sau 5 ngày kể từ hạn đóng (tức từ Ngày 15 hằng tháng - overdue_date),
    nếu hóa đơn chưa thanh toán (UNPAID), tự động chuyển trạng thái sang 'OVERDUE' ("Quá hạn (Nợ)").
    """
    today = date.today()
    unpaid_invoices = db.query(Invoice).filter(Invoice.status == "UNPAID").all()
    count = 0
    for inv in unpaid_invoices:
        overdue_threshold = inv.overdue_date or (inv.due_date + timedelta(days=5))
        if today > inv.due_date and today >= overdue_threshold:
            inv.status = "OVERDUE"
            count += 1
    if count > 0:
        db.commit()
    return count


def get_invoice_by_id(db: Session, invoice_id: int) -> Optional[Invoice]:
    """Retrieve invoice by ID."""
    return db.query(Invoice).filter(Invoice.id == invoice_id).first()


def get_invoices(
    db: Session,
    status: Optional[str] = None,
    month_year: Optional[str] = None,
    room_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Invoice]:
    """Retrieve list of invoices with filters."""
    check_and_update_overdue_invoices(db)

    query = db.query(Invoice)
    if status:
        query = query.filter(Invoice.status == status.upper())
    if month_year:
        query = query.filter(Invoice.month_year == month_year)
    if room_id:
        query = query.filter(Invoice.room_id == room_id)
    if tenant_id:
        query = query.filter(Invoice.tenant_id == tenant_id)

    return (
        query.order_by(Invoice.month_year.desc(), Invoice.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_tenant_invoices(db: Session, tenant_id: int, room_id: Optional[int] = None) -> List[Invoice]:
    """Retrieve all invoices strictly isolated for a tenant / room."""
    check_and_update_overdue_invoices(db)
    query = db.query(Invoice)
    if room_id:
        query = query.filter((Invoice.room_id == room_id) | (Invoice.tenant_id == tenant_id))
    else:
        query = query.filter(Invoice.tenant_id == tenant_id)
    return query.order_by(Invoice.month_year.desc(), Invoice.id.desc()).all()


def generate_monthly_invoices(
    db: Session,
    month_year: str,
    issue_date: Optional[date] = None,
    due_date: Optional[date] = None,
    send_email: bool = True,
) -> List[Invoice]:
    """
    Luồng tích hợp tự động:
    Đến kỳ thu tiền -> Lấy thông tin Hợp đồng đang hiệu lực + Chỉ số điện nước (Số mới - Số cũ)
    + Các phụ phí cố định của phòng (Gửi xe, Rác, Wifi, Bảo trì điện nước) -> Tính tổng tiền
    -> Tự động tạo Hóa đơn -> Gửi thông báo Real-time & Gmail cho đúng phòng đó (cô lập dữ liệu).
    """
    actual_issue_date = issue_date or date.today()
    if due_date:
        actual_due_date = due_date
    else:
        # Hạn đóng tiền cố định: Ngày 10 hằng tháng
        try:
            y_str, m_str = month_year.split("-")
            actual_due_date = date(int(y_str), int(m_str), 10)
        except Exception:
            actual_due_date = actual_issue_date + timedelta(days=10)

    actual_overdue_date = actual_due_date + timedelta(days=5)  # Ngày 15 hằng tháng

    active_contracts = (
        db.query(Contract)
        .filter(Contract.status == "ACTIVE")
        .all()
    )

    generated_invoices = []

    for contract in active_contracts:
        room = contract.room
        tenant = contract.tenant

        # 1. Lấy chỉ số điện nước của đúng phòng đó trong tháng month_year
        reading = (
            db.query(UtilityReading)
            .filter(
                UtilityReading.room_id == contract.room_id,
                UtilityReading.month_year == month_year,
            )
            .first()
        )

        old_elec = reading.old_electricity if reading else 0.0
        new_elec = reading.new_electricity if reading else 0.0
        elec_usage = max(0.0, new_elec - old_elec)

        old_water = reading.old_water if reading else 0.0
        new_water = reading.new_water if reading else 0.0
        water_usage = max(0.0, new_water - old_water)

        elec_rate = contract.electricity_rate
        elec_charge = round(elec_usage * elec_rate, 2)

        water_rate = contract.water_rate
        water_charge = round(water_usage * water_rate, 2)

        room_charge = contract.monthly_rent

        # Phụ phí tách mục rõ ràng
        parking_fee = contract.parking_fee if contract.parking_fee is not None else (room.parking_fee if room else 100000.0)
        trash_fee = contract.trash_fee if contract.trash_fee is not None else (room.trash_fee if room else 30000.0)
        wifi_fee = contract.wifi_fee if contract.wifi_fee is not None else (room.wifi_fee if room else 50000.0)
        maintenance_fee = contract.maintenance_fee if contract.maintenance_fee is not None else (room.maintenance_fee if room else 20000.0)

        service_charge = contract.service_fee if contract.service_fee is not None else (
            parking_fee + trash_fee + wifi_fee + maintenance_fee
        )
        other_charge = 0.0
        discount = 0.0

        total_amount = round(
            room_charge + elec_charge + water_charge + service_charge + other_charge - discount,
            2,
        )

        existing_invoice = (
            db.query(Invoice)
            .filter(
                Invoice.contract_id == contract.id,
                Invoice.month_year == month_year,
            )
            .first()
        )

        room_num = room.room_number if room else str(contract.room_id)

        if existing_invoice:
            if existing_invoice.status == "PAID":
                generated_invoices.append(existing_invoice)
                continue

            existing_invoice.room_charge = room_charge
            existing_invoice.old_electricity = old_elec
            existing_invoice.new_electricity = new_elec
            existing_invoice.electricity_usage = elec_usage
            existing_invoice.electricity_rate = elec_rate
            existing_invoice.electricity_charge = elec_charge
            existing_invoice.old_water = old_water
            existing_invoice.new_water = new_water
            existing_invoice.water_usage = water_usage
            existing_invoice.water_rate = water_rate
            existing_invoice.water_charge = water_charge
            existing_invoice.parking_fee = parking_fee
            existing_invoice.trash_fee = trash_fee
            existing_invoice.wifi_fee = wifi_fee
            existing_invoice.maintenance_fee = maintenance_fee
            existing_invoice.service_charge = service_charge
            existing_invoice.total_amount = total_amount
            existing_invoice.issue_date = actual_issue_date
            existing_invoice.due_date = actual_due_date
            existing_invoice.overdue_date = actual_overdue_date
            target_inv = existing_invoice
        else:
            clean_month = month_year.replace("-", "")
            invoice_code = f"INV-{room_num}-{clean_month}"

            conflict = db.query(Invoice).filter(Invoice.invoice_code == invoice_code).first()
            if conflict:
                invoice_code = f"{invoice_code}-{contract.id}"

            target_inv = Invoice(
                invoice_code=invoice_code,
                room_id=contract.room_id,
                contract_id=contract.id,
                tenant_id=contract.tenant_id,
                month_year=month_year,
                issue_date=actual_issue_date,
                due_date=actual_due_date,
                overdue_date=actual_overdue_date,
                room_charge=room_charge,
                old_electricity=old_elec,
                new_electricity=new_elec,
                electricity_usage=elec_usage,
                electricity_rate=elec_rate,
                electricity_charge=elec_charge,
                old_water=old_water,
                new_water=new_water,
                water_usage=water_usage,
                water_rate=water_rate,
                water_charge=water_charge,
                parking_fee=parking_fee,
                trash_fee=trash_fee,
                wifi_fee=wifi_fee,
                maintenance_fee=maintenance_fee,
                service_charge=service_charge,
                other_charge=other_charge,
                discount=discount,
                total_amount=total_amount,
                status="UNPAID",
                notes=f"Hóa đơn tiền phòng & điện nước kỳ {month_year} (Hạn đóng: ngày 10 hằng tháng)",
            )
            db.add(target_inv)

        generated_invoices.append(target_inv)

    db.commit()
    for inv in generated_invoices:
        db.refresh(inv)
        room_num = inv.room.room_number if inv.room else str(inv.room_id)
        if inv.status != "PAID":
            create_notification(
                db,
                recipient_role="TENANT",
                recipient_user_id=inv.tenant_id,
                room_id=inv.room_id,
                title=f"Hóa đơn mới kỳ {inv.month_year} - Phòng {room_num}",
                message=(
                    f"Chủ trọ đã phát hành hóa đơn {inv.invoice_code} kỳ {inv.month_year}. "
                    f"Tổng cộng: {inv.total_amount:,.0f}đ. Hạn đóng: {inv.due_date.strftime('%d/%m/%Y')}."
                ),
                notif_type="INVOICE_CREATED",
                related_id=inv.id,
            )
            if send_email:
                try:
                    send_invoice_email(db, inv, email_type="INVOICE_ISSUED")
                except Exception:
                    pass

    return generated_invoices


def pay_invoice(
    db: Session,
    invoice_id: int,
    payment_method: str = "MOMO",
    transaction_ref: Optional[str] = None,
    notes: Optional[str] = None,
) -> Invoice:
    """
    Phương thức 1 - Thanh toán Online (Momo, Thẻ Visa, Ngân hàng liên kết) hoặc thanh toán trực tiếp:
    - Xử lý giả lập thành công ngay lập tức (100% full payment).
    - Tự động gạch nợ / đổi trạng thái hóa đơn sang 'PAID'.
    - Gửi thông báo Real-time cho Chủ trọ & Khách thuê.
    - Tự động gửi Hóa đơn PDF đã thanh toán vào Gmail khách thuê.
    """
    invoice = get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hóa đơn ID {invoice_id}",
        )

    if invoice.status == "PAID":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hóa đơn này đã được thanh toán đầy đủ trước đó",
        )

    was_overdue = invoice.status == "OVERDUE"
    now = datetime.now(timezone.utc)
    method_upper = (payment_method or "MOMO").upper()
    tx_ref = transaction_ref or f"{method_upper}-{now.strftime('%Y%m%d%H%M%S')}-{invoice.id}"

    invoice.status = "PAID"
    invoice.paid_date = date.today()
    invoice.paid_at = now
    invoice.payment_method = method_upper
    invoice.transaction_ref = tx_ref
    invoice.is_reconciled = True

    if notes:
        existing_notes = f"{invoice.notes}\n" if invoice.notes else ""
        invoice.notes = f"{existing_notes}[Thanh toán {method_upper}]: {notes}"

    db.commit()
    db.refresh(invoice)

    room_num = invoice.room.room_number if invoice.room else str(invoice.room_id)
    action_label = "trả nợ tháng cũ" if was_overdue else "đóng tiền phòng"

    # Thông báo cho Chủ trọ
    create_notification(
        db,
        recipient_role="LANDLORD",
        room_id=invoice.room_id,
        title=f"Phòng {room_num} vừa {action_label} kỳ {invoice.month_year}",
        message=(
            f"Phòng {room_num} đã thanh toán thành công {invoice.total_amount:,.0f}đ "
            f"cho hóa đơn {invoice.invoice_code} qua cổng {method_upper} (Mã GD: {tx_ref})."
        ),
        notif_type="PAYMENT_SUCCESS",
        related_id=invoice.id,
    )

    # Thông báo cho Phòng đó
    create_notification(
        db,
        recipient_role="TENANT",
        recipient_user_id=invoice.tenant_id,
        room_id=invoice.room_id,
        title=f"Thanh toán thành công hóa đơn {invoice.invoice_code}",
        message=(
            f"Đã gạch nợ hóa đơn kỳ {invoice.month_year} ({invoice.total_amount:,.0f}đ) qua {method_upper}. "
            f"Biên lai PDF đã được gửi vào Gmail của phòng."
        ),
        notif_type="PAYMENT_SUCCESS",
        related_id=invoice.id,
    )

    # Tự động gửi Hóa đơn PDF đã thanh toán qua Gmail khách thuê
    try:
        send_invoice_email(db, invoice, email_type="PAYMENT_RECEIPT")
    except Exception:
        pass

    return invoice


def upload_invoice_bill(
    db: Session,
    invoice_id: int,
    bill_image_url: str,
    notes: Optional[str] = None,
) -> Invoice:
    """
    Phương thức 2 - Chuyển khoản Ngân hàng (VietQR) & Tải ảnh chụp màn hình Bill (UNC) lên hệ thống.
    - Chuyển trạng thái hóa đơn sang 'PENDING_APPROVAL' (Chờ chủ trọ duyệt bill).
    - Gửi thông báo Real-time cho Chủ trọ.
    """
    invoice = get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hóa đơn ID {invoice_id}",
        )
    if invoice.status == "PAID":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hóa đơn này đã được thanh toán",
        )

    invoice.bill_image_url = bill_image_url
    invoice.bill_uploaded_at = datetime.now(timezone.utc)
    invoice.status = "PENDING_APPROVAL"
    invoice.payment_method = "BANK_TRANSFER"
    if notes:
        existing_notes = f"{invoice.notes}\n" if invoice.notes else ""
        invoice.notes = f"{existing_notes}[Khách gửi Bill UNC]: {notes}"

    db.commit()
    db.refresh(invoice)

    room_num = invoice.room.room_number if invoice.room else str(invoice.room_id)
    create_notification(
        db,
        recipient_role="LANDLORD",
        room_id=invoice.room_id,
        title=f"Phòng {room_num} vừa gửi ảnh Bill chuyển khoản (Chờ duyệt)",
        message=(
            f"Khách thuê Phòng {room_num} đã tải lên ảnh UNC chuyển khoản cho hóa đơn {invoice.invoice_code} "
            f"kỳ {invoice.month_year} ({invoice.total_amount:,.0f}đ). Vui lòng kiểm tra và xác nhận thu tiền."
        ),
        notif_type="BILL_UPLOADED",
        related_id=invoice.id,
    )
    return invoice


def reconcile_demo_transaction(db: Session, invoice_id: int) -> dict:
    """
    Nút 'Kiểm tra / Đối soát giao dịch Demo' cho Chủ trọ:
    Xác nhận số tiền chuyển khoản đã khớp vào Tài khoản Ngân hàng của Chủ trọ.
    """
    invoice = get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hóa đơn",
        )
    room_num = invoice.room.room_number if invoice.room else str(invoice.room_id)
    tx_ref = invoice.transaction_ref or f"VCB-FT{datetime.now().strftime('%y%m%d')}{invoice.id:04d}"
    invoice.is_reconciled = True
    invoice.transaction_ref = tx_ref
    db.commit()
    db.refresh(invoice)
    return {
        "invoice_id": invoice.id,
        "invoice_code": invoice.invoice_code,
        "room_number": room_num,
        "matched_amount": invoice.total_amount,
        "bank_name": "Vietcombank (VCB) - TK: 1029384756",
        "transaction_ref": tx_ref,
        "transfer_content": f"PHONG {room_num} TT {invoice.month_year}",
        "is_reconciled": True,
        "message": f"Đối soát thành công: Đã nhận đúng {invoice.total_amount:,.0f} VNĐ từ Phòng {room_num} (Mã GD: {tx_ref}).",
    }


def approve_invoice_bill(
    db: Session,
    invoice_id: int,
    notes: Optional[str] = None,
) -> Invoice:
    """
    Chủ trọ bấm 'Xác nhận đã thu tiền' sau khi kiểm tra ảnh Bill chuyển khoản:
    - Đánh dấu hóa đơn sang 'PAID'.
    - Tạo thông báo Real-time cho Phòng đó.
    - Tự động gửi biên lai PDF qua Gmail của Phòng đó.
    """
    invoice = get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hóa đơn",
        )
    if invoice.status == "PAID":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hóa đơn này đã được xác nhận thu tiền trước đó",
        )

    now = datetime.now(timezone.utc)
    tx_ref = invoice.transaction_ref or f"VCB-UNC-{now.strftime('%Y%m%d%H%M')}-{invoice.id}"
    invoice.status = "PAID"
    invoice.paid_date = date.today()
    invoice.paid_at = now
    invoice.payment_method = "BANK_TRANSFER"
    invoice.transaction_ref = tx_ref
    invoice.is_reconciled = True

    if notes:
        existing_notes = f"{invoice.notes}\n" if invoice.notes else ""
        invoice.notes = f"{existing_notes}[Chủ trọ duyệt Bill]: {notes}"

    db.commit()
    db.refresh(invoice)

    room_num = invoice.room.room_number if invoice.room else str(invoice.room_id)
    create_notification(
        db,
        recipient_role="TENANT",
        recipient_user_id=invoice.tenant_id,
        room_id=invoice.room_id,
        title=f"Chủ trọ đã xác nhận thu tiền Phòng {room_num}",
        message=(
            f"Bill chuyển khoản của bạn cho hóa đơn {invoice.invoice_code} kỳ {invoice.month_year} "
            f"({invoice.total_amount:,.0f}đ) đã được duyệt. Biên lai PDF đã gửi vào Gmail."
        ),
        notif_type="PAYMENT_SUCCESS",
        related_id=invoice.id,
    )

    try:
        send_invoice_email(db, invoice, email_type="PAYMENT_RECEIPT")
    except Exception:
        pass

    return invoice

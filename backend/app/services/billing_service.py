from datetime import date, timedelta
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.invoice import Invoice
from app.models.contract import Contract
from app.models.room import Room
from app.models.utility_reading import UtilityReading
from app.schemas.invoice import InvoiceCreateManual


def check_and_update_overdue_invoices(db: Session) -> int:
    """
    Check all UNPAID invoices and automatically mark as OVERDUE
    if the due date has passed.
    """
    today = date.today()
    overdue_invoices = (
        db.query(Invoice)
        .filter(Invoice.status == "UNPAID", Invoice.due_date < today)
        .all()
    )
    count = 0
    for inv in overdue_invoices:
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
    # Ensure overdue statuses are current
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


def get_tenant_invoices(db: Session, tenant_id: int) -> List[Invoice]:
    """Retrieve all invoices associated with a tenant."""
    check_and_update_overdue_invoices(db)
    return (
        db.query(Invoice)
        .filter(Invoice.tenant_id == tenant_id)
        .order_by(Invoice.month_year.desc(), Invoice.id.desc())
        .all()
    )


def generate_monthly_invoices(
    db: Session,
    month_year: str,
    issue_date: Optional[date] = None,
    due_date: Optional[date] = None,
) -> List[Invoice]:
    """
    Automatically generate monthly invoices for all rooms with ACTIVE contracts.
    Formula:
    total_amount = room_charge + electricity_charge + water_charge + service_charge
    where:
      electricity_charge = electricity_usage * electricity_rate
      water_charge = water_usage * water_rate
    Status is initialized to UNPAID. Full payment only (no partial payment).
    """
    actual_issue_date = issue_date or date.today()
    actual_due_date = due_date or (actual_issue_date + timedelta(days=10))

    active_contracts = (
        db.query(Contract)
        .filter(Contract.status == "ACTIVE")
        .all()
    )

    generated_invoices = []

    for contract in active_contracts:
        room = contract.room
        tenant = contract.tenant

        # 1. Fetch utility reading for this room and month_year
        reading = (
            db.query(UtilityReading)
            .filter(
                UtilityReading.room_id == contract.room_id,
                UtilityReading.month_year == month_year,
            )
            .first()
        )

        elec_usage = 0.0
        water_usage = 0.0
        if reading:
            elec_usage = max(0.0, reading.new_electricity - reading.old_electricity)
            water_usage = max(0.0, reading.new_water - reading.old_water)

        elec_rate = contract.electricity_rate
        elec_charge = round(elec_usage * elec_rate, 2)

        water_rate = contract.water_rate
        water_charge = round(water_usage * water_rate, 2)

        room_charge = contract.monthly_rent
        service_charge = contract.service_fee
        other_charge = 0.0
        discount = 0.0

        total_amount = round(
            room_charge + elec_charge + water_charge + service_charge + other_charge - discount,
            2,
        )

        # 2. Check if invoice already exists for this contract and month
        existing_invoice = (
            db.query(Invoice)
            .filter(
                Invoice.contract_id == contract.id,
                Invoice.month_year == month_year,
            )
            .first()
        )

        if existing_invoice:
            # If already paid, do not overwrite
            if existing_invoice.status == "PAID":
                generated_invoices.append(existing_invoice)
                continue

            # Update existing unpaid/overdue invoice
            existing_invoice.room_charge = room_charge
            existing_invoice.electricity_usage = elec_usage
            existing_invoice.electricity_rate = elec_rate
            existing_invoice.electricity_charge = elec_charge
            existing_invoice.water_usage = water_usage
            existing_invoice.water_rate = water_rate
            existing_invoice.water_charge = water_charge
            existing_invoice.service_charge = service_charge
            existing_invoice.total_amount = total_amount
            existing_invoice.issue_date = actual_issue_date
            existing_invoice.due_date = actual_due_date
            generated_invoices.append(existing_invoice)
        else:
            clean_month = month_year.replace("-", "")
            invoice_code = f"INV-{room.room_number if room else contract.room_id}-{clean_month}"

            # Ensure uniqueness of invoice_code if regenerating
            conflict = db.query(Invoice).filter(Invoice.invoice_code == invoice_code).first()
            if conflict:
                invoice_code = f"{invoice_code}-{contract.id}"

            new_invoice = Invoice(
                invoice_code=invoice_code,
                room_id=contract.room_id,
                contract_id=contract.id,
                tenant_id=contract.tenant_id,
                month_year=month_year,
                issue_date=actual_issue_date,
                due_date=actual_due_date,
                room_charge=room_charge,
                electricity_usage=elec_usage,
                electricity_rate=elec_rate,
                electricity_charge=elec_charge,
                water_usage=water_usage,
                water_rate=water_rate,
                water_charge=water_charge,
                service_charge=service_charge,
                other_charge=other_charge,
                discount=discount,
                total_amount=total_amount,
                status="UNPAID",
            )
            db.add(new_invoice)
            generated_invoices.append(new_invoice)

    db.commit()
    for inv in generated_invoices:
        db.refresh(inv)

    return generated_invoices


def pay_invoice(
    db: Session,
    invoice_id: int,
    payment_method: str = "CASH",
    notes: Optional[str] = None,
) -> Invoice:
    """
    Process full payment for an invoice.
    Rule: Full payment only, immediately marks status as 'PAID'.
    No partial payments allowed.
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

    invoice.status = "PAID"
    invoice.paid_date = date.today()
    invoice.payment_method = payment_method.upper()

    if notes:
        existing_notes = f"{invoice.notes}\n" if invoice.notes else ""
        invoice.notes = f"{existing_notes}[Thanh toán {payment_method}]: {notes}"

    db.commit()
    db.refresh(invoice)
    return invoice

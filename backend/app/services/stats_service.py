from datetime import date
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.archived_tenant import ArchivedTenant
from app.models.contract import Contract
from app.models.feedback import Feedback
from app.models.invoice import Invoice
from app.models.room import Room
from app.models.user import User
from app.schemas.stats import (
    DashboardStatsResponse,
    MonthlyRevenueItem,
    OverdueInvoiceItem,
    RevenueStatsResponse,
)
from app.services.billing_service import check_and_update_overdue_invoices


def get_dashboard_stats(db: Session, month_year: Optional[str] = None) -> DashboardStatsResponse:
    """
    Compute real-time dashboard statistics for Landlord Portal.
    """
    check_and_update_overdue_invoices(db)

    total_rooms = db.query(func.count(Room.id)).scalar() or 0
    available_rooms = db.query(func.count(Room.id)).filter(Room.status == "AVAILABLE").scalar() or 0
    rented_rooms = db.query(func.count(Room.id)).filter(Room.status == "RENTED").scalar() or 0
    maintenance_rooms = db.query(func.count(Room.id)).filter(Room.status == "MAINTENANCE").scalar() or 0

    total_tenants = db.query(func.count(User.id)).filter(User.role == "TENANT").scalar() or 0
    active_contracts = db.query(func.count(Contract.id)).filter(Contract.status == "ACTIVE").scalar() or 0

    unpaid_invoices_count = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.status == "UNPAID")
        .scalar()
        or 0
    )
    pending_approval_count = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.status == "PENDING_APPROVAL")
        .scalar()
        or 0
    )
    paid_invoices_count = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.status == "PAID")
        .scalar()
        or 0
    )
    overdue_invoices_count = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.status == "OVERDUE")
        .scalar()
        or 0
    )

    unread_feedbacks_count = (
        db.query(func.count(Feedback.id))
        .filter(Feedback.is_read_by_admin == False)  # noqa: E712
        .scalar()
        or 0
    )
    archived_tenants_count = (
        db.query(func.count(ArchivedTenant.id))
        .scalar()
        or 0
    )

    target_month = month_year or date.today().strftime("%Y-%m")

    monthly_expected = (
        db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0))
        .filter(Invoice.month_year == target_month)
        .scalar()
    )
    monthly_actual = (
        db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0))
        .filter(Invoice.month_year == target_month, Invoice.status == "PAID")
        .scalar()
    )

    # Nếu tháng hiện tại chưa có hóa đơn nào (do test ở tháng khác), fallback lấy tổng kỳ gần nhất
    if float(monthly_expected or 0.0) == 0.0:
        latest_m = (
            db.query(Invoice.month_year)
            .order_by(Invoice.month_year.desc())
            .first()
        )
        if latest_m:
            monthly_expected = (
                db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0))
                .filter(Invoice.month_year == latest_m[0])
                .scalar()
            )
            monthly_actual = (
                db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0))
                .filter(Invoice.month_year == latest_m[0], Invoice.status == "PAID")
                .scalar()
            )

    total_unpaid = (
        db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0))
        .filter(Invoice.status.in_(["UNPAID", "PENDING_APPROVAL", "OVERDUE"]))
        .scalar()
    )

    return DashboardStatsResponse(
        total_rooms=total_rooms,
        available_rooms=available_rooms,
        rented_rooms=rented_rooms,
        maintenance_rooms=maintenance_rooms,
        total_tenants=total_tenants,
        active_contracts=active_contracts,
        unpaid_invoices_count=unpaid_invoices_count,
        pending_approval_invoices_count=pending_approval_count,
        paid_invoices_count=paid_invoices_count,
        overdue_invoices_count=overdue_invoices_count,
        unread_feedbacks_count=unread_feedbacks_count,
        archived_tenants_count=archived_tenants_count,
        monthly_expected_revenue=float(monthly_expected or 0.0),
        monthly_actual_revenue=float(monthly_actual or 0.0),
        total_unpaid_amount=float(total_unpaid or 0.0),
    )


def get_revenue_stats(db: Session) -> RevenueStatsResponse:
    """Compute aggregate collected vs unpaid revenue and per-month breakdowns."""
    check_and_update_overdue_invoices(db)

    total_collected = (
        db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0))
        .filter(Invoice.status == "PAID")
        .scalar()
    )
    total_unpaid = (
        db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0))
        .filter(Invoice.status.in_(["UNPAID", "PENDING_APPROVAL", "OVERDUE"]))
        .scalar()
    )

    months = (
        db.query(Invoice.month_year)
        .distinct()
        .order_by(Invoice.month_year.asc())
        .all()
    )

    monthly_breakdown: List[MonthlyRevenueItem] = []
    for (m_year,) in months:
        expected = (
            db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0))
            .filter(Invoice.month_year == m_year)
            .scalar()
        )
        collected = (
            db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0))
            .filter(Invoice.month_year == m_year, Invoice.status == "PAID")
            .scalar()
        )
        unpaid = (
            db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0))
            .filter(Invoice.month_year == m_year, Invoice.status.in_(["UNPAID", "PENDING_APPROVAL", "OVERDUE"]))
            .scalar()
        )
        monthly_breakdown.append(
            MonthlyRevenueItem(
                month_year=m_year,
                expected_amount=float(expected),
                collected_amount=float(collected),
                unpaid_amount=float(unpaid),
            )
        )

    return RevenueStatsResponse(
        total_collected_revenue=float(total_collected),
        total_unpaid_revenue=float(total_unpaid),
        monthly_breakdown=monthly_breakdown,
    )


def get_overdue_invoices(db: Session, month_year: Optional[str] = None) -> List[OverdueInvoiceItem]:
    """
    Mục 'Kiểm tra công nợ': Liệt kê chi tiết phòng nào đang nợ tiền của tháng nào, số tiền bao nhiêu.
    """
    check_and_update_overdue_invoices(db)
    today = date.today()

    query = db.query(Invoice).filter(Invoice.status == "OVERDUE")
    if month_year:
        query = query.filter(Invoice.month_year == month_year)

    overdue_invoices = query.order_by(Invoice.month_year.desc(), Invoice.due_date.asc()).all()

    result = []
    for inv in overdue_invoices:
        days_diff = (today - inv.due_date).days if inv.due_date else 0
        result.append(
            OverdueInvoiceItem(
                id=inv.id,
                invoice_code=inv.invoice_code,
                room_id=inv.room_id,
                room_number=inv.room.room_number if inv.room else None,
                floor=inv.room.floor if inv.room else 1,
                tenant_id=inv.tenant_id,
                tenant_name=inv.tenant.full_name if inv.tenant else None,
                tenant_phone=inv.tenant.phone if inv.tenant else None,
                tenant_email=inv.tenant.email if inv.tenant else None,
                month_year=inv.month_year,
                total_amount=inv.total_amount,
                due_date=inv.due_date,
                overdue_date=inv.overdue_date,
                days_overdue=max(0, days_diff),
                status=inv.status,
            )
        )
    return result

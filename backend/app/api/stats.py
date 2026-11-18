from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_landlord
from app.models.invoice import Invoice
from app.models.user import User
from app.schemas.stats import (
    DashboardStatsResponse,
    OverdueInvoiceItem,
    RevenueStatsResponse,
)
from app.services.cron_service import run_all_cronjobs
from app.services.notification_service import create_notification
from app.services.pdf_email_service import send_invoice_email
from app.services.stats_service import (
    get_dashboard_stats,
    get_overdue_invoices,
    get_revenue_stats,
)

router = APIRouter()


@router.get("/dashboard", response_model=DashboardStatsResponse)
def dashboard_overview(
    month_year: Optional[str] = Query(None, description="Tháng thống kê (YYYY-MM)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Thống kê tổng quan cho Dashboard chủ trọ."""
    return get_dashboard_stats(db, month_year=month_year)


@router.get("/revenue", response_model=RevenueStatsResponse)
def revenue_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Báo cáo chi tiết doanh thu theo từng tháng (Phải thu, Đã thu, Còn nợ)."""
    return get_revenue_stats(db)


@router.get("/overdue", response_model=List[OverdueInvoiceItem])
def overdue_overview(
    month_year: Optional[str] = Query(None, description="Lọc theo tháng (YYYY-MM)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Mục 'Kiểm tra công nợ': Liệt kê chi tiết phòng nào đang nợ tiền của tháng nào, số tiền bao nhiêu.
    """
    return get_overdue_invoices(db, month_year=month_year)


@router.post("/overdue/{invoice_id}/remind")
def remind_overdue_room(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Gửi thông báo Real-time & Gmail nhắc hạn thanh toán nợ cho đúng phòng đang nợ."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn")

    room_num = inv.room.room_number if inv.room else str(inv.room_id)
    create_notification(
        db,
        recipient_role="TENANT",
        recipient_user_id=inv.tenant_id,
        room_id=inv.room_id,
        title=f"Nhắc thanh toán nợ quá hạn - Phòng {room_num}",
        message=(
            f"Chủ trọ nhắc bạn thanh toán hóa đơn quá hạn {inv.invoice_code} kỳ {inv.month_year} "
            f"với số tiền {inv.total_amount:,.0f}đ. Vui lòng vào mục 'Thanh toán nợ' để đóng tiền."
        ),
        notif_type="OVERDUE_ALERT",
        related_id=inv.id,
    )
    log_entry = send_invoice_email(db, inv, email_type="OVERDUE_REMINDER")
    return {
        "message": f"Đã gửi thông báo nhắc nợ & Gmail tới Phòng {room_num} ({log_entry.recipient_email})",
        "invoice_code": inv.invoice_code,
        "room_number": room_num,
    }


@router.post("/run-cron")
def execute_cronjobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Chạy các tác vụ Cronjob tự động:
    1. Xóa vĩnh viễn hồ sơ khách thuê trong mục Lưu trữ tạm đã quá 30 ngày.
    2. Tự động đánh dấu Quá hạn (Nợ) cho các hóa đơn chưa thanh toán sau ngày 15 hằng tháng.
    """
    return run_all_cronjobs(db)

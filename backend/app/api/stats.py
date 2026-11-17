from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_landlord
from app.models.user import User
from app.schemas.stats import (
    DashboardStatsResponse,
    RevenueStatsResponse,
    OverdueInvoiceItem,
)
from app.services.stats_service import (
    get_dashboard_stats,
    get_revenue_stats,
    get_overdue_invoices,
)

router = APIRouter()


@router.get("/dashboard", response_model=DashboardStatsResponse)
def dashboard_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Thống kê tổng quan cho Dashboard chủ trọ:
    - Số lượng phòng theo trạng thái (trống, đã thuê, bảo trì)
    - Số lượng khách thuê, số hợp đồng đang hoạt động
    - Tình hình hóa đơn (chưa thanh toán, đã thanh toán, quá hạn)
    - Doanh thu dự kiến, thực thu tháng hiện tại và tổng nợ tồn đọng.
    """
    return get_dashboard_stats(db)


@router.get("/revenue", response_model=RevenueStatsResponse)
def revenue_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Báo cáo chi tiết doanh thu:
    - Tổng doanh thu thực thu lũy kế
    - Tổng nợ cần thu
    - Phân tích chi tiết doanh thu theo từng tháng (dự kiến, thực thu, còn nợ).
    """
    return get_revenue_stats(db)


@router.get("/overdue", response_model=List[OverdueInvoiceItem])
def overdue_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Danh sách các hóa đơn quá hạn chưa thanh toán kèm thông tin liên hệ của khách thuê
    và số ngày quá hạn (phục vụ thu hồi nợ).
    """
    return get_overdue_invoices(db)

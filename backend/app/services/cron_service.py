from datetime import date, datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.archived_tenant import ArchivedTenant
from app.models.invoice import Invoice
from app.services.notification_service import create_notification
from app.services.pdf_email_service import send_invoice_email


def cleanup_expired_archived_tenants(db: Session) -> int:
    """
    Cronjob 1: Xóa vĩnh viễn hồ sơ khách thuê cũ trong mục Lưu trữ tạm (Archived)
    sau khi đã lưu giữ đủ 30 ngày (1 tháng) kể từ lúc trả phòng (deleted_at).
    """
    now = datetime.now(timezone.utc)
    cutoff_30_days = now - timedelta(days=30)

    expired_records = (
        db.query(ArchivedTenant)
        .filter(
            (ArchivedTenant.expire_at <= now)
            | (ArchivedTenant.deleted_at <= cutoff_30_days)
        )
        .all()
    )

    deleted_count = 0
    for rec in expired_records:
        db.delete(rec)
        deleted_count += 1

    if deleted_count > 0:
        db.commit()
    return deleted_count


def mark_overdue_invoices_after_day_15(db: Session, reference_date: date = None) -> int:
    """
    Cronjob 2: Kiểm tra hạn thanh toán hóa đơn:
    - Hạn đóng tiền cố định: Ngày 10 hằng tháng.
    - Sau 5 ngày kể từ hạn đóng (tức từ Ngày 15 hằng tháng), nếu hóa đơn chưa thanh toán (UNPAID),
      tự động chuyển trạng thái sang 'OVERDUE' ("Quá hạn (Nợ)"), đánh dấu đỏ phòng đó và gửi nhắc nợ.
    """
    today = reference_date or date.today()
    unpaid_invoices = db.query(Invoice).filter(Invoice.status == "UNPAID").all()

    overdue_count = 0
    for inv in unpaid_invoices:
        # Tính mốc quá hạn: overdue_date (mặc định là due_date + 5 ngày, tức ngày 15 của tháng)
        threshold_date = inv.overdue_date or (inv.due_date + timedelta(days=5))
        if today >= threshold_date:
            inv.status = "OVERDUE"
            overdue_count += 1
            room_num = inv.room.room_number if inv.room else str(inv.room_id)
            create_notification(
                db,
                recipient_role="TENANT",
                recipient_user_id=inv.tenant_id,
                room_id=inv.room_id,
                title=f"Cảnh báo Quá hạn (Nợ) - Phòng {room_num}",
                message=(
                    f"Hóa đơn {inv.invoice_code} kỳ {inv.month_year} ({inv.total_amount:,.0f}đ) đã quá hạn ngày 15. "
                    f"Vui lòng vào mục 'Thanh toán nợ' để đóng tiền."
                ),
                notif_type="OVERDUE_ALERT",
                related_id=inv.id,
                commit=False,
            )
            create_notification(
                db,
                recipient_role="LANDLORD",
                room_id=inv.room_id,
                title=f"Phòng {room_num} quá hạn thanh toán sau ngày 15",
                message=(
                    f"Phòng {room_num} chưa đóng hóa đơn kỳ {inv.month_year} ({inv.total_amount:,.0f}đ) sau ngày 15. "
                    f"Hệ thống đã chuyển sang trạng thái Quá hạn (Nợ)."
                ),
                notif_type="OVERDUE_ALERT",
                related_id=inv.id,
                commit=False,
            )
            try:
                send_invoice_email(db, inv, email_type="OVERDUE_REMINDER")
            except Exception:
                pass

    if overdue_count > 0:
        db.commit()
    return overdue_count


def run_all_cronjobs(db: Session) -> dict:
    """Chạy toàn bộ các tác vụ tự động (Cronjob 30 ngày & Đánh dấu nợ ngày 15)."""
    purged_tenants = cleanup_expired_archived_tenants(db)
    newly_overdue = mark_overdue_invoices_after_day_15(db)
    return {
        "purged_archived_tenants": purged_tenants,
        "newly_marked_overdue_invoices": newly_overdue,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }

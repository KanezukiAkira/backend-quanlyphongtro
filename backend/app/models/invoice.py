from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    invoice_code = Column(String(100), unique=True, index=True, nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True)
    tenant_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    month_year = Column(String(7), nullable=False, index=True)  # Format: 'YYYY-MM'
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)  # Hạn đóng cố định: Ngày 10 hằng tháng
    overdue_date = Column(Date, nullable=True)  # Sau 5 ngày kể từ hạn đóng: Ngày 15 hằng tháng

    # Tiền phòng cơ bản
    room_charge = Column(Float, nullable=False, default=2000000.0)

    # Tiền điện: (Số mới - Số cũ) * Đơn giá điện
    old_electricity = Column(Float, nullable=False, default=0.0)
    new_electricity = Column(Float, nullable=False, default=0.0)
    electricity_usage = Column(Float, nullable=False, default=0.0)
    electricity_rate = Column(Float, nullable=False, default=3500.0)
    electricity_charge = Column(Float, nullable=False, default=0.0)

    # Tiền nước: (Số mới - Số cũ) * Đơn giá nước
    old_water = Column(Float, nullable=False, default=0.0)
    new_water = Column(Float, nullable=False, default=0.0)
    water_usage = Column(Float, nullable=False, default=0.0)
    water_rate = Column(Float, nullable=False, default=20000.0)
    water_charge = Column(Float, nullable=False, default=0.0)

    # Các khoản phụ phí tách mục rõ ràng
    parking_fee = Column(Float, nullable=False, default=100000.0)  # Tiền gửi xe
    trash_fee = Column(Float, nullable=False, default=30000.0)  # Tiền rác/vệ sinh
    wifi_fee = Column(Float, nullable=False, default=50000.0)  # Tiền Wifi
    maintenance_fee = Column(Float, nullable=False, default=20000.0)  # Tiền bảo trì điện nước
    service_charge = Column(Float, nullable=False, default=200000.0)  # Tổng phụ phí dịch vụ

    other_charge = Column(Float, nullable=False, default=0.0)
    discount = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)

    # Trạng thái: 'UNPAID' (Chờ đóng), 'PENDING_APPROVAL' (Chờ duyệt bill UNC), 'PAID' (Đã đóng), 'OVERDUE' (Quá hạn sau ngày 15 / Nợ)
    status = Column(String(50), nullable=False, default="UNPAID")
    paid_date = Column(Date, nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    payment_method = Column(String(100), nullable=True)  # 'MOMO', 'VISA', 'LINKED_BANK', 'BANK_TRANSFER', 'CASH'
    transaction_ref = Column(String(100), nullable=True)

    # Phương thức 2: Chuyển khoản ngân hàng & Upload ảnh Bill (UNC)
    bill_image_url = Column(Text, nullable=True)
    bill_uploaded_at = Column(DateTime(timezone=True), nullable=True)
    is_reconciled = Column(Boolean, nullable=False, default=False)  # Đối soát giao dịch Demo

    # Trạng thái gửi Hóa đơn/Biên lai PDF qua Gmail
    email_sent = Column(Boolean, nullable=False, default=False)
    email_sent_at = Column(DateTime(timezone=True), nullable=True)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    room = relationship("Room", back_populates="invoices")
    contract = relationship("Contract", back_populates="invoices")
    tenant = relationship("User", back_populates="invoices")

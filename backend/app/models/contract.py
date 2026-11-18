from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    contract_code = Column(String(100), unique=True, index=True, nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    deposit_amount = Column(Float, nullable=False, default=2000000.0)
    monthly_rent = Column(Float, nullable=False, default=2000000.0)

    # Đơn giá điện nước & các khoản phụ phí theo hợp đồng
    electricity_rate = Column(Float, nullable=False, default=3500.0)
    water_rate = Column(Float, nullable=False, default=20000.0)
    parking_fee = Column(Float, nullable=False, default=100000.0)
    trash_fee = Column(Float, nullable=False, default=30000.0)
    wifi_fee = Column(Float, nullable=False, default=50000.0)
    maintenance_fee = Column(Float, nullable=False, default=20000.0)
    service_fee = Column(Float, nullable=False, default=200000.0)  # Tổng phụ phí cố định

    payment_due_day = Column(Integer, nullable=False, default=10)  # Ngày 10 hằng tháng

    # Thông tin Bên A (Chủ nhà trọ) phục vụ xuất Hợp đồng Pháp lý Việt Nam
    landlord_name = Column(String(255), nullable=False, default="Nguyễn Minh Hoàng")
    landlord_cccd = Column(String(50), nullable=False, default="079085001234")
    landlord_phone = Column(String(50), nullable=False, default="0901234567")
    landlord_address = Column(
        String(500),
        nullable=False,
        default="Số 128 Nguyễn Văn Cừ, Phường 4, Quận 5, TP. Hồ Chí Minh"
    )

    status = Column(String(50), nullable=False, default="ACTIVE")  # 'ACTIVE', 'EXPIRED', 'TERMINATED'
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    room = relationship("Room", back_populates="contracts")
    tenant = relationship("User", back_populates="contracts")
    invoices = relationship("Invoice", back_populates="contract")

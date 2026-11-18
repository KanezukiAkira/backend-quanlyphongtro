from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_number = Column(String(50), unique=True, index=True, nullable=False)  # Ví dụ: '1.1', '2.3', '3.5'
    floor = Column(Integer, nullable=False, default=1, index=True)  # Số tầng: 1, 2, 3...
    room_seq = Column(Integer, nullable=False, default=1)  # Số thứ tự phòng trong tầng: 1..5
    price = Column(Float, nullable=False, default=2000000.0)  # Mặc định 2.000.000 VNĐ/tháng
    area = Column(Float, nullable=True, default=22.0)
    max_occupants = Column(Integer, nullable=False, default=2)
    status = Column(String(50), nullable=False, default="AVAILABLE")  # 'AVAILABLE', 'RENTED', 'MAINTENANCE'

    # Đơn giá điện nước & Phụ phí cố định theo phòng
    electricity_rate = Column(Float, nullable=False, default=3500.0)  # đ/kWh
    water_rate = Column(Float, nullable=False, default=20000.0)  # đ/m3
    parking_fee = Column(Float, nullable=False, default=100000.0)  # Tiền gửi xe
    trash_fee = Column(Float, nullable=False, default=30000.0)  # Tiền rác / vệ sinh
    wifi_fee = Column(Float, nullable=False, default=50000.0)  # Tiền Wifi
    maintenance_fee = Column(Float, nullable=False, default=20000.0)  # Tiền bảo trì điện nước

    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    contracts = relationship("Contract", back_populates="room", cascade="all, delete-orphan")
    utility_readings = relationship("UtilityReading", back_populates="room", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="room", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="room", cascade="all, delete-orphan")

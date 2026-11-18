from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), unique=True, index=True, nullable=False)  # 'admin' hoặc '1.1', '2.3'...
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    gender = Column(String(30), nullable=True)  # 'Nam', 'Nữ', 'Khác'
    birth_date = Column(Date, nullable=True)  # Ngày sinh
    phone = Column(String(50), nullable=True)  # Số điện thoại
    email = Column(String(255), nullable=True)  # Gmail
    cccd = Column(String(50), nullable=True)  # Số CCCD (12 số)
    hometown = Column(String(255), nullable=True)  # Quê quán
    role = Column(String(50), nullable=False, default="TENANT")  # 'LANDLORD', 'TENANT'

    # Liên kết tài khoản phòng trực tiếp với Phòng
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True)
    is_profile_completed = Column(Boolean, nullable=False, default=False)

    # Quản lý phiên đăng nhập: tăng token_version sẽ thu hồi toàn bộ JWT/thiết bị đang đăng nhập ngay lập tức
    token_version = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    room = relationship("Room", foreign_keys=[room_id])
    contracts = relationship("Contract", back_populates="tenant", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="tenant")
    feedbacks = relationship("Feedback", back_populates="tenant", cascade="all, delete-orphan")

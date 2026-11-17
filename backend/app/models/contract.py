from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    contract_code = Column(String(100), unique=True, index=True, nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    deposit_amount = Column(Float, nullable=False, default=0.0)
    monthly_rent = Column(Float, nullable=False, default=0.0)
    electricity_rate = Column(Float, nullable=False, default=0.0)
    water_rate = Column(Float, nullable=False, default=0.0)
    service_fee = Column(Float, nullable=False, default=0.0)
    status = Column(String(50), nullable=False, default="ACTIVE")  # 'ACTIVE', 'EXPIRED', 'TERMINATED'
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    room = relationship("Room", back_populates="contracts")
    tenant = relationship("User", back_populates="contracts")
    invoices = relationship("Invoice", back_populates="contract")

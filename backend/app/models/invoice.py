from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    invoice_code = Column(String(100), unique=True, index=True, nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=True)
    tenant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month_year = Column(String(7), nullable=False, index=True)  # Format: 'YYYY-MM'
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    room_charge = Column(Float, nullable=False, default=0.0)
    electricity_usage = Column(Float, nullable=False, default=0.0)
    electricity_rate = Column(Float, nullable=False, default=0.0)
    electricity_charge = Column(Float, nullable=False, default=0.0)
    water_usage = Column(Float, nullable=False, default=0.0)
    water_rate = Column(Float, nullable=False, default=0.0)
    water_charge = Column(Float, nullable=False, default=0.0)
    service_charge = Column(Float, nullable=False, default=0.0)
    other_charge = Column(Float, nullable=False, default=0.0)
    discount = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    status = Column(String(50), nullable=False, default="UNPAID")  # 'UNPAID', 'PAID', 'OVERDUE' (No partial payment!)
    paid_date = Column(Date, nullable=True)
    payment_method = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    room = relationship("Room", back_populates="invoices")
    contract = relationship("Contract", back_populates="invoices")
    tenant = relationship("User", back_populates="invoices")

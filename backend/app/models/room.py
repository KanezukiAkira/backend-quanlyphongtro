from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_number = Column(String(50), unique=True, index=True, nullable=False)
    price = Column(Float, nullable=False, default=0.0)
    area = Column(Float, nullable=True)
    max_occupants = Column(Integer, nullable=False, default=2)
    status = Column(String(50), nullable=False, default="AVAILABLE")  # 'AVAILABLE', 'RENTED', 'MAINTENANCE'
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    contracts = relationship("Contract", back_populates="room")
    utility_readings = relationship("UtilityReading", back_populates="room", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="room")

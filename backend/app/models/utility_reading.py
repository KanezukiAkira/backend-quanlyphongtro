from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class UtilityReading(Base):
    __tablename__ = "utility_readings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    month_year = Column(String(7), nullable=False, index=True)  # Format: 'YYYY-MM'
    recorded_date = Column(Date, nullable=False)
    old_electricity = Column(Float, nullable=False, default=0.0)
    new_electricity = Column(Float, nullable=False, default=0.0)
    old_water = Column(Float, nullable=False, default=0.0)
    new_water = Column(Float, nullable=False, default=0.0)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    room = relationship("Room", back_populates="utility_readings")
    recorder = relationship("User")

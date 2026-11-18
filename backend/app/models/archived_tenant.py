from sqlalchemy import Column, Integer, String, Date, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base


class ArchivedTenant(Base):
    __tablename__ = "archived_tenants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    original_user_id = Column(Integer, nullable=True)
    room_id = Column(Integer, nullable=True)
    room_number = Column(String(50), nullable=False, index=True)
    username = Column(String(100), nullable=True)

    full_name = Column(String(255), nullable=False)
    gender = Column(String(30), nullable=True)
    birth_date = Column(Date, nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    cccd = Column(String(50), nullable=True)
    hometown = Column(String(255), nullable=True)

    contract_code = Column(String(100), nullable=True)
    check_in_date = Column(Date, nullable=True)
    check_out_date = Column(Date, nullable=True)
    checkout_reason = Column(Text, nullable=True)

    status = Column(String(50), nullable=False, default="ARCHIVED")
    deleted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    expire_at = Column(DateTime(timezone=True), nullable=False, index=True)  # deleted_at + 30 days

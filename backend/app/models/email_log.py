from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    recipient_email = Column(String(255), nullable=False)
    recipient_name = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=False)
    attachment_name = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="SENT")  # 'SENT', 'DEMO_LOGGED', 'FAILED'
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

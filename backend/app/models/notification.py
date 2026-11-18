from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recipient_role = Column(String(50), nullable=False, index=True)  # 'LANDLORD' hoặc 'TENANT'
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    # Loại sự kiện: 'PAYMENT_SUCCESS', 'BILL_UPLOADED', 'INVOICE_CREATED', 'OVERDUE_ALERT', 'FEEDBACK_NEW', 'FEEDBACK_REPLY', 'SYSTEM'
    type = Column(String(50), nullable=False, default="INFO")
    related_id = Column(Integer, nullable=True)

    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Phân loại: 'ELECTRIC_WATER' (Điện nước), 'SECURITY' (An ninh), 'HYGIENE' (Vệ sinh), 'GENERAL' (Góp ý chung)
    category = Column(String(50), nullable=False, default="GENERAL")
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)

    # Trạng thái: 'UNREAD' (Cần đọc - đẩy lên đầu danh sách), 'READ' (Đã xem), 'RESOLVED' (Đã phản hồi)
    status = Column(String(50), nullable=False, default="UNREAD")
    is_read_by_admin = Column(Boolean, nullable=False, default=False)
    is_reply_read_by_tenant = Column(Boolean, nullable=False, default=True)

    admin_reply = Column(Text, nullable=True)
    replied_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    room = relationship("Room", back_populates="feedbacks")
    tenant = relationship("User", back_populates="feedbacks")

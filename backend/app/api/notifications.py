from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationResponse
from app.services.notification_service import (
    get_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)

router = APIRouter()


@router.get("", response_model=List[NotificationResponse])
@router.get("/", response_model=List[NotificationResponse], include_in_schema=False)
def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lấy danh sách thông báo Real-time cho người dùng đang đăng nhập (Chủ trọ hoặc Phòng khách thuê).
    Phục vụ biểu tượng Chiếc chuông (Bell Icon) & Popup Toast 10 giây.
    """
    return get_user_notifications(db, current_user, limit=limit)


@router.put("/read-all")
def read_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đánh dấu tất cả thông báo là đã đọc."""
    count = mark_all_notifications_read(db, current_user)
    return {"message": "Đã đánh dấu đọc tất cả thông báo", "updated_count": count}


@router.put("/{id}/read", response_model=NotificationResponse)
def read_single_notification(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đánh dấu 1 thông báo là đã đọc."""
    return mark_notification_read(db, id, current_user)

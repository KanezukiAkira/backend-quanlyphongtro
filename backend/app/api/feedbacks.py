from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_landlord
from app.models.user import User
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackReplyRequest,
    FeedbackResponse,
)
from app.services.feedback_service import (
    create_feedback,
    list_feedbacks_for_admin,
    list_feedbacks_for_tenant,
    mark_feedback_read,
    reply_to_feedback,
)

router = APIRouter()


@router.get("", response_model=List[FeedbackResponse])
@router.get("/", response_model=List[FeedbackResponse], include_in_schema=False)
def get_all_feedbacks(
    room_id: Optional[int] = Query(None, description="Lọc theo ID phòng"),
    category: Optional[str] = Query(None, description="ELECTRIC_WATER, SECURITY, HYGIENE, GENERAL"),
    unread_only: bool = Query(False, description="Chỉ lấy các phản ánh chưa đọc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Lấy danh sách Feedback trên trang Admin của Chủ trọ:
    Khi có phòng gửi Feedback mới (chưa đọc), phòng đó tự động được đẩy lên đầu danh sách
    và gắn nhãn nổi bật 'Cần đọc (Chưa đọc)'.
    """
    return list_feedbacks_for_admin(db, room_id=room_id, category=category, unread_only=unread_only)


@router.get("/my-feedbacks", response_model=List[FeedbackResponse])
def get_my_feedbacks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Khách thuê xem danh sách Feedback & phản hồi từ Chủ trọ của phòng mình."""
    return list_feedbacks_for_tenant(db, current_user)


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def submit_feedback(
    fb_in: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Khách thuê gửi Feedback / Báo hỏng / Đóng góp ý kiến mới."""
    return create_feedback(db, fb_in, current_user)


@router.put("/{id}/read", response_model=FeedbackResponse)
def read_feedback(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Chủ trọ đánh dấu đã xem Feedback."""
    return mark_feedback_read(db, id)


@router.post("/{id}/reply", response_model=FeedbackResponse)
def reply_feedback(
    id: int,
    reply_in: FeedbackReplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Chủ trọ gửi phản hồi trực tiếp cho phòng đã gửi Feedback."""
    return reply_to_feedback(db, id, reply_in)

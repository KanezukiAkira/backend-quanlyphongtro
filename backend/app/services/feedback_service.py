from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session
from app.models.feedback import Feedback
from app.models.room import Room
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackReplyRequest, FeedbackResponse
from app.services.notification_service import create_notification


def enrich_feedback(db: Session, fb: Feedback) -> FeedbackResponse:
    room = fb.room or db.query(Room).filter(Room.id == fb.room_id).first()
    tenant = fb.tenant or db.query(User).filter(User.id == fb.tenant_id).first()
    return FeedbackResponse(
        id=fb.id,
        room_id=fb.room_id,
        room_number=room.room_number if room else str(fb.room_id),
        floor=room.floor if room else 1,
        tenant_id=fb.tenant_id,
        tenant_name=tenant.full_name if tenant else "Khách thuê",
        tenant_phone=tenant.phone if tenant else None,
        category=fb.category,
        title=fb.title,
        content=fb.content,
        status=fb.status,
        is_read_by_admin=fb.is_read_by_admin,
        is_reply_read_by_tenant=fb.is_reply_read_by_tenant,
        admin_reply=fb.admin_reply,
        replied_at=fb.replied_at,
        created_at=fb.created_at,
    )


def create_feedback(db: Session, fb_in: FeedbackCreate, current_user: User) -> FeedbackResponse:
    """
    Khách thuê gửi Feedback / Báo hỏng / Góp ý mới.
    - Trạng thái ban đầu: 'UNREAD', is_read_by_admin=False -> Tự động đẩy lên đầu danh sách Admin với nhãn "Cần đọc (Chưa đọc)".
    - Tạo thông báo Real-time cho Chủ trọ.
    """
    room_id = current_user.room_id
    if not room_id:
        # Nếu user chưa gắn room_id trực tiếp thì tìm qua username (VD: '1.1') hoặc hợp đồng
        room_by_num = db.query(Room).filter(Room.room_number == current_user.username).first()
        if room_by_num:
            room_id = room_by_num.id
    if not room_id:
        first_room = db.query(Room).first()
        room_id = first_room.id if first_room else 1

    room = db.query(Room).filter(Room.id == room_id).first()
    room_num = room.room_number if room else str(room_id)

    fb = Feedback(
        room_id=room_id,
        tenant_id=current_user.id,
        category=fb_in.category.upper(),
        title=fb_in.title,
        content=fb_in.content,
        status="UNREAD",
        is_read_by_admin=False,
        is_reply_read_by_tenant=True,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    create_notification(
        db,
        recipient_role="LANDLORD",
        room_id=room_id,
        title=f"Phòng {room_num} gửi Góp ý/Phản ánh mới [Cần đọc]",
        message=f"[{fb.category}] {fb.title}: {fb.content[:100]}",
        notif_type="FEEDBACK_NEW",
        related_id=fb.id,
    )

    return enrich_feedback(db, fb)


def list_feedbacks_for_admin(
    db: Session,
    room_id: Optional[int] = None,
    category: Optional[str] = None,
    unread_only: bool = False,
) -> List[FeedbackResponse]:
    """
    Lấy danh sách Feedback cho Chủ trọ:
    - Những phòng có Feedback mới (is_read_by_admin == False) tự động được đẩy lên đầu danh sách!
    """
    query = db.query(Feedback)
    if room_id:
        query = query.filter(Feedback.room_id == room_id)
    if category:
        query = query.filter(Feedback.category == category.upper())
    if unread_only:
        query = query.filter(Feedback.is_read_by_admin == False)  # noqa: E712

    # Ưu tiên chưa đọc (is_read_by_admin=False -> 0) lên đầu, sau đó mới nhất
    items = (
        query.order_by(asc(Feedback.is_read_by_admin), desc(Feedback.created_at), desc(Feedback.id))
        .all()
    )
    return [enrich_feedback(db, f) for f in items]


def list_feedbacks_for_tenant(db: Session, current_user: User) -> List[FeedbackResponse]:
    query = db.query(Feedback)
    if current_user.room_id:
        query = query.filter(Feedback.room_id == current_user.room_id)
    else:
        query = query.filter(Feedback.tenant_id == current_user.id)
    items = query.order_by(desc(Feedback.created_at), desc(Feedback.id)).all()
    return [enrich_feedback(db, f) for f in items]


def mark_feedback_read(db: Session, feedback_id: int) -> FeedbackResponse:
    fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not fb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phản ánh/góp ý",
        )
    fb.is_read_by_admin = True
    if fb.status == "UNREAD":
        fb.status = "READ"
    db.commit()
    db.refresh(fb)
    return enrich_feedback(db, fb)


def reply_to_feedback(db: Session, feedback_id: int, reply_in: FeedbackReplyRequest) -> FeedbackResponse:
    """
    Chủ trọ gửi phản hồi trực tiếp cho phòng đã gửi Feedback.
    Tự động đánh dấu đã đọc và bắn thông báo Real-time (Toast 10s + Bell) về đúng phòng đó.
    """
    fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not fb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phản ánh/góp ý",
        )

    fb.admin_reply = reply_in.admin_reply
    fb.replied_at = datetime.now(timezone.utc)
    fb.is_read_by_admin = True
    fb.is_reply_read_by_tenant = False
    fb.status = "RESOLVED"
    db.commit()
    db.refresh(fb)

    room = fb.room or db.query(Room).filter(Room.id == fb.room_id).first()
    room_num = room.room_number if room else str(fb.room_id)

    create_notification(
        db,
        recipient_role="TENANT",
        recipient_user_id=fb.tenant_id,
        room_id=fb.room_id,
        title=f"Chủ trọ đã phản hồi góp ý của Phòng {room_num}",
        message=f"Phản hồi về '{fb.title}': {fb.admin_reply}",
        notif_type="FEEDBACK_REPLY",
        related_id=fb.id,
    )

    return enrich_feedback(db, fb)

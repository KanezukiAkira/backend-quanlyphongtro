from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.models.room import Room
from app.models.user import User
from app.schemas.notification import NotificationResponse


def create_notification(
    db: Session,
    recipient_role: str,
    title: str,
    message: str,
    notif_type: str = "INFO",
    recipient_user_id: Optional[int] = None,
    room_id: Optional[int] = None,
    related_id: Optional[int] = None,
    commit: bool = True,
) -> Notification:
    """
    Create a notification for either LANDLORD or a specific TENANT room/account.
    Guarantees strict room/tenant data isolation.
    """
    notif = Notification(
        recipient_role=recipient_role.upper(),
        recipient_user_id=recipient_user_id,
        room_id=room_id,
        title=title,
        message=message,
        type=notif_type,
        related_id=related_id,
        is_read=False,
    )
    db.add(notif)
    if commit:
        db.commit()
        db.refresh(notif)
    return notif


def enrich_notification(db: Session, notif: Notification) -> NotificationResponse:
    room_number = None
    if notif.room_id:
        room = db.query(Room).filter(Room.id == notif.room_id).first()
        if room:
            room_number = room.room_number
    return NotificationResponse(
        id=notif.id,
        recipient_role=notif.recipient_role,
        recipient_user_id=notif.recipient_user_id,
        room_id=notif.room_id,
        room_number=room_number,
        title=notif.title,
        message=notif.message,
        type=notif.type,
        related_id=notif.related_id,
        is_read=notif.is_read,
        created_at=notif.created_at,
    )


def get_user_notifications(
    db: Session,
    current_user: User,
    limit: int = 50,
) -> List[NotificationResponse]:
    """
    Retrieve notifications strictly isolated for the current user:
    - LANDLORD receives all notifications with recipient_role == 'LANDLORD'
    - TENANT receives only notifications matching their recipient_user_id or room_id
    """
    query = db.query(Notification)
    if current_user.role == "LANDLORD":
        query = query.filter(Notification.recipient_role == "LANDLORD")
    else:
        conditions = [Notification.recipient_user_id == current_user.id]
        if current_user.room_id:
            conditions.append(
                (Notification.recipient_role == "TENANT")
                & (Notification.room_id == current_user.room_id)
            )
        query = query.filter(
            Notification.recipient_role == "TENANT",
            or_(*conditions),
        )

    items = query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit).all()
    return [enrich_notification(db, n) for n in items]


def mark_notification_read(db: Session, notification_id: int, current_user: User) -> NotificationResponse:
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy thông báo",
        )
    if current_user.role != "LANDLORD":
        if notif.recipient_user_id != current_user.id and notif.room_id != current_user.room_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền truy cập thông báo này",
            )
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return enrich_notification(db, notif)


def mark_all_notifications_read(db: Session, current_user: User) -> int:
    query = db.query(Notification).filter(Notification.is_read == False)  # noqa: E712
    if current_user.role == "LANDLORD":
        query = query.filter(Notification.recipient_role == "LANDLORD")
    else:
        conditions = [Notification.recipient_user_id == current_user.id]
        if current_user.room_id:
            conditions.append(Notification.room_id == current_user.room_id)
        query = query.filter(
            Notification.recipient_role == "TENANT",
            or_(*conditions),
        )
    updated = query.update({"is_read": True}, synchronize_session=False)
    db.commit()
    return updated

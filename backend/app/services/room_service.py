from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.room import Room
from app.models.contract import Contract
from app.schemas.room import RoomCreate, RoomUpdate


def get_rooms(
    db: Session,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Room]:
    """Retrieve list of rooms with optional status filter."""
    query = db.query(Room)
    if status:
        query = query.filter(Room.status == status.upper())
    return query.order_by(Room.room_number.asc()).offset(skip).limit(limit).all()


def get_room_by_id(db: Session, room_id: int) -> Optional[Room]:
    """Retrieve room by ID."""
    return db.query(Room).filter(Room.id == room_id).first()


def get_room_by_number(db: Session, room_number: str) -> Optional[Room]:
    """Retrieve room by room number."""
    return db.query(Room).filter(Room.room_number == room_number).first()


def create_room(db: Session, room_in: RoomCreate) -> Room:
    """Create a new rental room."""
    existing = get_room_by_number(db, room_in.room_number)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phòng số '{room_in.room_number}' đã tồn tại",
        )

    room = Room(
        room_number=room_in.room_number,
        price=room_in.price,
        area=room_in.area,
        max_occupants=room_in.max_occupants,
        status=room_in.status.upper() if room_in.status else "AVAILABLE",
        description=room_in.description,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def update_room(db: Session, room_id: int, room_in: RoomUpdate) -> Room:
    """Update room details."""
    room = get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phòng",
        )

    update_data = room_in.model_dump(exclude_unset=True)
    if "room_number" in update_data and update_data["room_number"] != room.room_number:
        existing = get_room_by_number(db, update_data["room_number"])
        if existing and existing.id != room_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Phòng số '{update_data['room_number']}' đã tồn tại",
            )

    if "status" in update_data and update_data["status"]:
        update_data["status"] = update_data["status"].upper()

    for field, value in update_data.items():
        setattr(room, field, value)

    db.commit()
    db.refresh(room)
    return room


def delete_room(db: Session, room_id: int) -> bool:
    """Delete a room if it does not have active contracts."""
    room = get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phòng",
        )

    active_contract = (
        db.query(Contract)
        .filter(Contract.room_id == room_id, Contract.status == "ACTIVE")
        .first()
    )
    if active_contract or room.status == "RENTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa phòng đang có hợp đồng hoạt động hoặc đang được thuê",
        )

    db.delete(room)
    db.commit()
    return True

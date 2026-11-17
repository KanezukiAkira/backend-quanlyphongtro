from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_landlord
from app.models.user import User
from app.schemas.room import RoomCreate, RoomUpdate, RoomResponse
from app.services.room_service import (
    get_rooms,
    get_room_by_id,
    create_room,
    update_room,
    delete_room,
)

router = APIRouter()


@router.get("", response_model=List[RoomResponse])
@router.get("/", response_model=List[RoomResponse], include_in_schema=False)
def list_rooms(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: AVAILABLE, RENTED, MAINTENANCE"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Lấy danh sách các phòng trọ (có thể lọc theo trạng thái)."""
    return get_rooms(db, status=status, skip=skip, limit=limit)


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def add_room(
    room_in: RoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Thêm phòng trọ mới (chỉ chủ trọ)."""
    return create_room(db, room_in)


@router.get("/{id}", response_model=RoomResponse)
def get_room(
    id: int,
    db: Session = Depends(get_db),
):
    """Xem chi tiết một phòng trọ theo ID."""
    room = get_room_by_id(db, id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phòng có ID {id}",
        )
    return room


@router.put("/{id}", response_model=RoomResponse)
def modify_room(
    id: int,
    room_in: RoomUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Cập nhật thông tin phòng trọ (chỉ chủ trọ)."""
    return update_room(db, id, room_in)


@router.delete("/{id}")
def remove_room(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Xóa phòng trọ (chỉ chủ trọ, chỉ xóa phòng không có hợp đồng hoạt động)."""
    delete_room(db, id)
    return {"message": "Đã xóa phòng thành công", "room_id": id}

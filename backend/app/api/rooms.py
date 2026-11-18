from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_landlord
from app.models.user import User
from app.schemas.room import (
    FloorCreateRequest,
    RoomCheckoutRequest,
    RoomCreate,
    RoomResponse,
    RoomUpdate,
)
from app.services.room_service import (
    checkout_and_reset_room_account,
    create_floor_with_rooms,
    create_room,
    delete_room,
    enrich_room_response,
    get_room_by_id,
    get_rooms,
    update_room,
)

router = APIRouter()


@router.get("", response_model=List[RoomResponse])
@router.get("/", response_model=List[RoomResponse], include_in_schema=False)
def list_rooms(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: AVAILABLE, RENTED, MAINTENANCE"),
    floor: Optional[int] = Query(None, description="Lọc theo số tầng (1, 2, 3...)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Lấy danh sách các phòng trọ kèm trạng thái thuê, hồ sơ khách, công nợ quá hạn."""
    return get_rooms(db, status=status, floor=floor, skip=skip, limit=limit)


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def add_room(
    room_in: RoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Thêm phòng trọ mới (chỉ chủ trọ).
    Tự động sinh tài khoản đăng nhập cho phòng theo định dạng [Số tầng].[Số thứ tự phòng].
    """
    return create_room(db, room_in)


@router.post("/add-floor", response_model=List[RoomResponse], status_code=status.HTTP_201_CREATED)
def add_floor(
    req: FloorCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Thêm tầng mới và tự động tạo các phòng kèm tài khoản đăng nhập [Tầng].[Thứ tự phòng]."""
    return create_floor_with_rooms(db, req)


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
    return enrich_room_response(db, room)


@router.put("/{id}", response_model=RoomResponse)
def modify_room(
    id: int,
    room_in: RoomUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Cập nhật thông tin phòng trọ, giá thuê cơ bản và các phụ phí cố định (chỉ chủ trọ)."""
    return update_room(db, id, room_in)


@router.post("/{id}/checkout")
def checkout_room(
    id: int,
    req: Optional[RoomCheckoutRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Quy trình Khách chuyển đi ('Khách trả phòng / Reset tài khoản'):
    - Đăng xuất toàn bộ các thiết bị đang đăng nhập vào tài khoản phòng đó (Invalidate JWT token_version).
    - Đặt lại mật khẩu mới để khách cũ không thể đăng nhập lại.
    - Chuyển toàn bộ hồ sơ khách cũ sang trạng thái Archived (Lưu trữ tạm 30 ngày trước khi tự động xóa).
    - Thanh lý hợp đồng và giải phóng phòng về trạng thái AVAILABLE.
    """
    checkout_req = req or RoomCheckoutRequest()
    return checkout_and_reset_room_account(db, id, checkout_req)


@router.delete("/{id}")
def remove_room(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Xóa phòng trọ (chỉ chủ trọ, chỉ xóa phòng không có hợp đồng hoạt động)."""
    delete_room(db, id)
    return {"message": "Đã xóa phòng thành công", "room_id": id}

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_landlord
from app.models.user import User
from app.schemas.utility import UtilityReadingCreate, UtilityReadingResponse
from app.services.utility_service import (
    get_last_reading,
    get_readings,
    get_reading_by_id,
    record_reading,
    enrich_reading_response,
)

router = APIRouter()


@router.get("/last-reading/{room_id}", response_model=UtilityReadingResponse)
def get_latest_room_reading(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy chỉ số điện nước ghi nhận gần nhất của một phòng."""
    reading = get_last_reading(db, room_id)
    if not reading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chưa có bản ghi chỉ số điện nước nào cho phòng ID {room_id}",
        )
    return enrich_reading_response(reading)


@router.post("", response_model=UtilityReadingResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=UtilityReadingResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_reading(
    reading_in: UtilityReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Ghi nhận chỉ số điện nước tháng cho phòng (chỉ chủ trọ).
    Tự động tính toán lượng tiêu thụ và đối chiếu với chỉ số cũ.
    """
    return record_reading(db, reading_in, recorded_by=current_user.id)


@router.get("", response_model=List[UtilityReadingResponse])
@router.get("/", response_model=List[UtilityReadingResponse], include_in_schema=False)
def list_readings(
    room_id: Optional[int] = Query(None, description="Lọc theo ID phòng"),
    month_year: Optional[str] = Query(None, description="Lọc theo tháng (YYYY-MM)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách các bản ghi chỉ số điện nước."""
    return get_readings(db, room_id=room_id, month_year=month_year, skip=skip, limit=limit)


@router.get("/{id}", response_model=UtilityReadingResponse)
def get_reading(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xem chi tiết một bản ghi chỉ số điện nước theo ID."""
    reading = get_reading_by_id(db, id)
    if not reading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bản ghi chỉ số có ID {id}",
        )
    return reading

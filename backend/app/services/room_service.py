from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.security import get_password_hash
from app.models.archived_tenant import ArchivedTenant
from app.models.contract import Contract
from app.models.invoice import Invoice
from app.models.room import Room
from app.models.user import User
from app.schemas.room import (
    FloorCreateRequest,
    RoomCheckoutRequest,
    RoomCreate,
    RoomResponse,
    RoomUpdate,
)
from app.services.notification_service import create_notification


def _parse_floor_and_seq(room_number: str, default_floor: int = 1, default_seq: int = 1):
    if "." in room_number:
        parts = room_number.split(".", 1)
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            pass
    return default_floor, default_seq


def enrich_room_response(db: Session, room: Room) -> RoomResponse:
    """Enrich Room with tenant profile, active contract, overdue debt status, and pending bills."""
    active_contract = (
        db.query(Contract)
        .filter(Contract.room_id == room.id, Contract.status == "ACTIVE")
        .order_by(Contract.id.desc())
        .first()
    )

    room_user = (
        db.query(User)
        .filter((User.room_id == room.id) | (User.username == room.room_number))
        .first()
    )

    tenant = active_contract.tenant if (active_contract and active_contract.tenant) else room_user

    # Check overdue invoices for this room
    overdue_invoices = (
        db.query(Invoice)
        .filter(Invoice.room_id == room.id, Invoice.status == "OVERDUE")
        .all()
    )
    overdue_amount = sum(float(i.total_amount or 0.0) for i in overdue_invoices)
    overdue_months_count = len(overdue_invoices)

    pending_bill_count = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.room_id == room.id, Invoice.status == "PENDING_APPROVAL")
        .scalar()
        or 0
    )

    return RoomResponse(
        id=room.id,
        room_number=room.room_number,
        floor=room.floor or 1,
        room_seq=room.room_seq or 1,
        price=room.price,
        area=room.area,
        max_occupants=room.max_occupants,
        status=room.status,
        electricity_rate=room.electricity_rate if room.electricity_rate is not None else 3500.0,
        water_rate=room.water_rate if room.water_rate is not None else 20000.0,
        parking_fee=room.parking_fee if room.parking_fee is not None else 100000.0,
        trash_fee=room.trash_fee if room.trash_fee is not None else 30000.0,
        wifi_fee=room.wifi_fee if room.wifi_fee is not None else 50000.0,
        maintenance_fee=room.maintenance_fee if room.maintenance_fee is not None else 20000.0,
        description=room.description,
        created_at=room.created_at,
        account_username=room_user.username if room_user else room.room_number,
        tenant_id=tenant.id if tenant else None,
        tenant_name=tenant.full_name if tenant else None,
        tenant_phone=tenant.phone if tenant else None,
        tenant_email=tenant.email if tenant else None,
        tenant_cccd=tenant.cccd if tenant else None,
        tenant_gender=tenant.gender if tenant else None,
        tenant_birth_date=tenant.birth_date.isoformat() if (tenant and tenant.birth_date) else None,
        tenant_hometown=tenant.hometown if tenant else None,
        is_profile_completed=bool(tenant.is_profile_completed) if tenant else False,
        has_overdue_invoice=overdue_months_count > 0,
        overdue_amount=round(overdue_amount, 2),
        overdue_months_count=overdue_months_count,
        pending_bill_count=pending_bill_count,
        active_contract_id=active_contract.id if active_contract else None,
    )


def get_rooms(
    db: Session,
    status: Optional[str] = None,
    floor: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[RoomResponse]:
    """Retrieve list of rooms with optional status and floor filter."""
    query = db.query(Room)
    if status:
        query = query.filter(Room.status == status.upper())
    if floor is not None:
        query = query.filter(Room.floor == floor)
    rooms = (
        query.order_by(Room.floor.asc(), Room.room_seq.asc(), Room.room_number.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [enrich_room_response(db, r) for r in rooms]


def get_room_by_id(db: Session, room_id: int) -> Optional[Room]:
    """Retrieve room by ID."""
    return db.query(Room).filter(Room.id == room_id).first()


def get_room_by_number(db: Session, room_number: str) -> Optional[Room]:
    """Retrieve room by room number."""
    return db.query(Room).filter(Room.room_number == room_number).first()


def _ensure_room_account(db: Session, room: Room, default_password: str = "123456") -> User:
    """
    Tự động sinh tài khoản độc lập cho phòng theo quy tắc [Số tầng].[Số thứ tự phòng trong tầng]
    (Ví dụ: '1.1', '2.3', '3.5').
    """
    existing_user = db.query(User).filter(User.username == room.room_number).first()
    if existing_user:
        if not existing_user.room_id:
            existing_user.room_id = room.id
            db.commit()
        return existing_user

    new_user = User(
        username=room.room_number,
        password_hash=get_password_hash(default_password or "123456"),
        full_name=f"Khách thuê Phòng {room.room_number}",
        role="TENANT",
        room_id=room.id,
        is_profile_completed=False,
        token_version=1,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def create_room(db: Session, room_in: RoomCreate) -> RoomResponse:
    """
    Create a new rental room and automatically generate its independent room account
    ([Số tầng].[Số thứ tự phòng trong tầng]).
    """
    room_num = room_in.room_number
    if not room_num:
        room_num = f"{room_in.floor}.{room_in.room_seq}"

    floor_val, seq_val = _parse_floor_and_seq(room_num, room_in.floor, room_in.room_seq)

    existing = get_room_by_number(db, room_num)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phòng số '{room_num}' đã tồn tại",
        )

    room = Room(
        room_number=room_num,
        floor=floor_val,
        room_seq=seq_val,
        price=room_in.price if room_in.price is not None else 2000000.0,
        area=room_in.area if room_in.area is not None else 22.0,
        max_occupants=room_in.max_occupants or 2,
        status=room_in.status.upper() if room_in.status else "AVAILABLE",
        electricity_rate=room_in.electricity_rate if room_in.electricity_rate is not None else 3500.0,
        water_rate=room_in.water_rate if room_in.water_rate is not None else 20000.0,
        parking_fee=room_in.parking_fee if room_in.parking_fee is not None else 100000.0,
        trash_fee=room_in.trash_fee if room_in.trash_fee is not None else 30000.0,
        wifi_fee=room_in.wifi_fee if room_in.wifi_fee is not None else 50000.0,
        maintenance_fee=room_in.maintenance_fee if room_in.maintenance_fee is not None else 20000.0,
        description=room_in.description or f"Phòng {room_num} (Tầng {floor_val}) khép kín, đầy đủ tiện nghi",
    )
    db.add(room)
    db.commit()
    db.refresh(room)

    # Tự động sinh tài khoản cho phòng
    _ensure_room_account(db, room, room_in.default_password or "123456")

    return enrich_room_response(db, room)


def create_floor_with_rooms(db: Session, req: FloorCreateRequest) -> List[RoomResponse]:
    """
    Thêm tầng mới và tự động tạo các phòng trong tầng kèm tài khoản [Tầng].[Thứ tự phòng].
    """
    created = []
    for seq in range(1, req.num_rooms + 1):
        r_num = f"{req.floor}.{seq}"
        if get_room_by_number(db, r_num):
            continue
        room_in = RoomCreate(
            room_number=r_num,
            floor=req.floor,
            room_seq=seq,
            price=req.base_price,
            area=req.area,
            max_occupants=2,
            status="AVAILABLE",
            description=f"Phòng {r_num} Tầng {req.floor} mới xây dựng",
            default_password=req.default_password,
        )
        created.append(create_room(db, room_in))
    return created


def update_room(db: Session, room_id: int, room_in: RoomUpdate) -> RoomResponse:
    """Update room details, base rent, and fixed surcharges."""
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

    # Đồng bộ giá thuê và phụ phí sang Hợp đồng đang hiệu lực nếu có
    active_contract = (
        db.query(Contract)
        .filter(Contract.room_id == room.id, Contract.status == "ACTIVE")
        .first()
    )
    if active_contract:
        if "price" in update_data and update_data["price"] is not None:
            active_contract.monthly_rent = room.price
        if "electricity_rate" in update_data and update_data["electricity_rate"] is not None:
            active_contract.electricity_rate = room.electricity_rate
        if "water_rate" in update_data and update_data["water_rate"] is not None:
            active_contract.water_rate = room.water_rate
        if any(k in update_data for k in ("parking_fee", "trash_fee", "wifi_fee", "maintenance_fee")):
            active_contract.parking_fee = room.parking_fee
            active_contract.trash_fee = room.trash_fee
            active_contract.wifi_fee = room.wifi_fee
            active_contract.maintenance_fee = room.maintenance_fee
            active_contract.service_fee = (
                (room.parking_fee or 0.0)
                + (room.trash_fee or 0.0)
                + (room.wifi_fee or 0.0)
                + (room.maintenance_fee or 0.0)
            )

    db.commit()
    db.refresh(room)
    return enrich_room_response(db, room)


def checkout_and_reset_room_account(
    db: Session,
    room_id: int,
    req: RoomCheckoutRequest,
) -> dict:
    """
    Quy trình Khách chuyển đi (Check-out & Bảo mật):
    1. Đăng xuất toàn bộ các thiết bị đang đăng nhập vào tài khoản phòng đó (token_version += 1).
    2. Đặt lại mật khẩu mới cho tài khoản phòng để khách cũ không thể đăng nhập lại.
    3. Lưu toàn bộ hồ sơ của khách thuê vừa chuyển đi sang trạng thái Archived (deleted_at, giữ 30 ngày trước khi xóa sạch).
    4. Thanh lý hợp đồng ACTIVE -> TERMINATED và trả trạng thái phòng về AVAILABLE.
    """
    room = get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phòng",
        )

    active_contract = (
        db.query(Contract)
        .filter(Contract.room_id == room.id, Contract.status == "ACTIVE")
        .order_by(Contract.id.desc())
        .first()
    )

    room_user = (
        db.query(User)
        .filter((User.room_id == room.id) | (User.username == room.room_number))
        .first()
    )
    tenant = active_contract.tenant if (active_contract and active_contract.tenant) else room_user

    now = datetime.now(timezone.utc)
    expire_at = now + timedelta(days=30)

    archived_record = None
    if tenant and (tenant.is_profile_completed or tenant.cccd or tenant.phone or active_contract):
        archived_record = ArchivedTenant(
            original_user_id=tenant.id,
            room_id=room.id,
            room_number=room.room_number,
            username=tenant.username,
            full_name=tenant.full_name,
            gender=tenant.gender,
            birth_date=tenant.birth_date,
            phone=tenant.phone,
            email=tenant.email,
            cccd=tenant.cccd,
            hometown=tenant.hometown,
            contract_code=active_contract.contract_code if active_contract else None,
            check_in_date=active_contract.start_date if active_contract else None,
            check_out_date=date.today(),
            checkout_reason=req.checkout_reason or "Khách trả phòng & kết thúc hợp đồng",
            status="ARCHIVED",
            deleted_at=now,
            expire_at=expire_at,
        )
        db.add(archived_record)

    # Kết thúc hợp đồng đang hiệu lực
    if active_contract:
        active_contract.status = "TERMINATED"
        note_append = f"[Trả phòng {date.today().strftime('%d/%m/%Y')}]: {req.checkout_reason or 'Khách chuyển đi'}"
        active_contract.notes = f"{active_contract.notes}\n{note_append}" if active_contract.notes else note_append

    # Thu hồi phiên đăng nhập (Invalidate JWT trên mọi thiết bị) & Reset mật khẩu + hồ sơ tài khoản phòng
    new_pwd = req.new_password or "123456"
    target_accounts = []
    if room_user:
        target_accounts.append(room_user)
    if tenant and tenant not in target_accounts and tenant.role == "TENANT":
        target_accounts.append(tenant)

    for acc in target_accounts:
        acc.token_version = (acc.token_version or 1) + 1
        acc.password_hash = get_password_hash(new_pwd)
        if acc.username == room.room_number or acc.room_id == room.id:
            acc.full_name = f"Phòng {room.room_number} (Chưa khai báo hồ sơ)"
            acc.gender = None
            acc.birth_date = None
            acc.phone = None
            acc.email = None
            acc.cccd = None
            acc.hometown = None
            acc.is_profile_completed = False

    room.status = "AVAILABLE"
    db.commit()
    if archived_record:
        db.refresh(archived_record)

    create_notification(
        db,
        recipient_role="LANDLORD",
        room_id=room.id,
        title=f"Đã hoàn tất trả phòng & Reset tài khoản Phòng {room.room_number}",
        message=(
            f"Đã thu hồi toàn bộ thiết bị đăng nhập của Phòng {room.room_number}, đặt lại mật khẩu mới "
            f"và chuyển hồ sơ khách cũ vào Lưu trữ tạm (tự động xóa sau 30 ngày)."
        ),
        notif_type="SYSTEM",
        related_id=room.id,
    )

    return {
        "message": f"Đã trả phòng {room.room_number}, thu hồi toàn bộ phiên đăng nhập và lưu trữ tạm hồ sơ khách cũ trong 30 ngày.",
        "room_id": room.id,
        "room_number": room.room_number,
        "revoked_sessions": True,
        "new_token_version": room_user.token_version if room_user else 2,
        "archived_tenant_id": archived_record.id if archived_record else None,
        "retain_days": 30,
    }


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
            detail="Không thể xóa phòng đang có khách thuê hoặc hợp đồng đang hiệu lực. Vui lòng thực hiện 'Khách trả phòng' trước.",
        )

    # Xóa tài khoản phòng gắn liền nếu có
    room_users = db.query(User).filter(
        (User.room_id == room.id) | (User.username == room.room_number),
        User.role == "TENANT",
    ).all()
    for u in room_users:
        db.delete(u)

    db.delete(room)
    db.commit()
    return True

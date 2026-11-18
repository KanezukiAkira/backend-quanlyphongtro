from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.contract import Contract
from app.models.room import Room
from app.models.user import User
from app.schemas.contract import ContractCreate
from app.services.notification_service import create_notification


def get_contracts(
    db: Session,
    status: Optional[str] = None,
    room_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Contract]:
    """Retrieve list of contracts with optional status/room filter."""
    query = db.query(Contract)
    if status:
        query = query.filter(Contract.status == status.upper())
    if room_id:
        query = query.filter(Contract.room_id == room_id)
    return query.order_by(Contract.id.desc()).offset(skip).limit(limit).all()


def get_contract_by_id(db: Session, contract_id: int) -> Optional[Contract]:
    """Retrieve contract by ID."""
    return db.query(Contract).filter(Contract.id == contract_id).first()


def get_contract_by_room(db: Session, room_id: int) -> Optional[Contract]:
    """Retrieve active or latest contract for a specific room."""
    active = (
        db.query(Contract)
        .filter(Contract.room_id == room_id, Contract.status == "ACTIVE")
        .order_by(Contract.id.desc())
        .first()
    )
    if active:
        return active
    return (
        db.query(Contract)
        .filter(Contract.room_id == room_id)
        .order_by(Contract.id.desc())
        .first()
    )


def get_tenant_contract(db: Session, tenant_id: int, room_id: Optional[int] = None) -> Optional[Contract]:
    """
    Retrieve active contract for a specific tenant or their assigned room.
    """
    active_contract = (
        db.query(Contract)
        .filter(Contract.tenant_id == tenant_id, Contract.status == "ACTIVE")
        .order_by(Contract.id.desc())
        .first()
    )
    if active_contract:
        return active_contract

    if room_id:
        room_contract = get_contract_by_room(db, room_id)
        if room_contract:
            return room_contract

    return (
        db.query(Contract)
        .filter(Contract.tenant_id == tenant_id)
        .order_by(Contract.id.desc())
        .first()
    )


def get_active_contracts(db: Session) -> List[Contract]:
    """Retrieve all currently active contracts."""
    return db.query(Contract).filter(Contract.status == "ACTIVE").all()


def create_contract(db: Session, contract_in: ContractCreate) -> Contract:
    """
    Create a new rental contract following Vietnamese legal template.
    - Auto-links room account if tenant_id is not explicitly passed.
    - Pulls room price and fixed surcharges from the Room if not overridden.
    - Automatically sets room status to 'RENTED'.
    """
    room = db.query(Room).filter(Room.id == contract_in.room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phòng có ID {contract_in.room_id}",
        )

    existing_room_contract = (
        db.query(Contract)
        .filter(Contract.room_id == room.id, Contract.status == "ACTIVE")
        .first()
    )
    if existing_room_contract and room.status == "RENTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phòng {room.room_number} hiện đang có hợp đồng hiệu lực ({existing_room_contract.contract_code})",
        )

    tenant = None
    if contract_in.tenant_id:
        tenant = db.query(User).filter(User.id == contract_in.tenant_id).first()
    else:
        tenant = (
            db.query(User)
            .filter((User.room_id == room.id) | (User.username == room.room_number))
            .first()
        )

    if not tenant or tenant.role != "TENANT":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tài khoản khách thuê hợp lệ",
        )

    existing_active = (
        db.query(Contract)
        .filter(Contract.tenant_id == tenant.id, Contract.status == "ACTIVE")
        .first()
    )
    if existing_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Khách thuê '{tenant.full_name}' hiện đã có hợp đồng thuê phòng khác còn hiệu lực",
        )

    if contract_in.end_date <= contract_in.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày kết thúc hợp đồng phải sau ngày bắt đầu",
        )

    timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
    contract_code = f"HD-{room.room_number}-{timestamp_str}"

    rent_amount = (
        contract_in.monthly_rent
        if contract_in.monthly_rent is not None
        else room.price
    )
    deposit_amount = (
        contract_in.deposit_amount
        if contract_in.deposit_amount is not None
        else rent_amount
    )

    elec_rate = contract_in.electricity_rate if contract_in.electricity_rate is not None else (room.electricity_rate or 3500.0)
    water_rate = contract_in.water_rate if contract_in.water_rate is not None else (room.water_rate or 20000.0)
    parking = contract_in.parking_fee if contract_in.parking_fee is not None else (room.parking_fee or 100000.0)
    trash = contract_in.trash_fee if contract_in.trash_fee is not None else (room.trash_fee or 30000.0)
    wifi = contract_in.wifi_fee if contract_in.wifi_fee is not None else (room.wifi_fee or 50000.0)
    maint = contract_in.maintenance_fee if contract_in.maintenance_fee is not None else (room.maintenance_fee or 20000.0)

    if contract_in.service_fee is not None:
        total_service_fee = contract_in.service_fee
    else:
        total_service_fee = parking + trash + wifi + maint

    contract = Contract(
        contract_code=contract_code,
        room_id=room.id,
        tenant_id=tenant.id,
        start_date=contract_in.start_date,
        end_date=contract_in.end_date,
        deposit_amount=deposit_amount,
        monthly_rent=rent_amount,
        electricity_rate=elec_rate,
        water_rate=water_rate,
        parking_fee=parking,
        trash_fee=trash,
        wifi_fee=wifi,
        maintenance_fee=maint,
        service_fee=total_service_fee,
        payment_due_day=contract_in.payment_due_day or 10,
        landlord_name=contract_in.landlord_name or "Nguyễn Minh Hoàng",
        landlord_cccd=contract_in.landlord_cccd or "079085001234",
        landlord_phone=contract_in.landlord_phone or "0901234567",
        landlord_address=contract_in.landlord_address or "Số 128 Nguyễn Văn Cừ, Phường 4, Quận 5, TP. Hồ Chí Minh",
        status="ACTIVE",
        notes=contract_in.notes,
    )
    db.add(contract)
    room.status = "RENTED"
    if not tenant.room_id:
        tenant.room_id = room.id

    db.commit()
    db.refresh(contract)

    create_notification(
        db,
        recipient_role="TENANT",
        recipient_user_id=tenant.id,
        room_id=room.id,
        title=f"Hợp đồng thuê phòng {room.room_number} đã được ban hành",
        message=f"Hợp đồng mã {contract.contract_code} có hiệu lực từ {contract.start_date.strftime('%d/%m/%Y')} đến {contract.end_date.strftime('%d/%m/%Y')}. Bạn có thể xem và tải PDF bất cứ lúc nào.",
        notif_type="SYSTEM",
        related_id=contract.id,
    )
    return contract


def terminate_contract(db: Session, contract_id: int, notes: Optional[str] = None) -> Contract:
    """
    Terminate an active contract and release the room back to AVAILABLE.
    """
    contract = get_contract_by_id(db, contract_id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hợp đồng ID {contract_id}",
        )
    if contract.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hợp đồng đã ở trạng thái {contract.status}, không thể kết thúc lại",
        )

    contract.status = "TERMINATED"
    if notes:
        existing_notes = f"{contract.notes}\n" if contract.notes else ""
        contract.notes = f"{existing_notes}[Đã thanh lý]: {notes}"

    if contract.room:
        contract.room.status = "AVAILABLE"

    db.commit()
    db.refresh(contract)
    return contract

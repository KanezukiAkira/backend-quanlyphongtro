from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.contract import Contract
from app.models.room import Room
from app.models.user import User
from app.schemas.contract import ContractCreate, ContractUpdate


def get_contracts(
    db: Session,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Contract]:
    """Retrieve list of contracts with optional status filter."""
    query = db.query(Contract)
    if status:
        query = query.filter(Contract.status == status.upper())
    return query.order_by(Contract.id.desc()).offset(skip).limit(limit).all()


def get_contract_by_id(db: Session, contract_id: int) -> Optional[Contract]:
    """Retrieve contract by ID."""
    return db.query(Contract).filter(Contract.id == contract_id).first()


def get_tenant_contract(db: Session, tenant_id: int) -> Optional[Contract]:
    """
    Retrieve active contract for a specific tenant.
    If no active contract found, returns the most recent contract.
    """
    active_contract = (
        db.query(Contract)
        .filter(Contract.tenant_id == tenant_id, Contract.status == "ACTIVE")
        .order_by(Contract.id.desc())
        .first()
    )
    if active_contract:
        return active_contract

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
    Create a new rental contract.
    - Validates room exists and is AVAILABLE.
    - Validates tenant exists with role TENANT and has no existing ACTIVE contract.
    - Automatically sets room status to 'RENTED'.
    - Generates unique contract_code.
    """
    # 1. Check room
    room = db.query(Room).filter(Room.id == contract_in.room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phòng có ID {contract_in.room_id}",
        )
    if room.status != "AVAILABLE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phòng {room.room_number} hiện không ở trạng thái sẵn sàng (Trạng thái: {room.status})",
        )

    # 2. Check tenant
    tenant = db.query(User).filter(User.id == contract_in.tenant_id).first()
    if not tenant or tenant.role != "TENANT":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tài khoản khách thuê có ID {contract_in.tenant_id}",
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

    # 3. Check dates
    if contract_in.end_date <= contract_in.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày kết thúc hợp đồng phải sau ngày bắt đầu",
        )

    # 4. Generate contract code
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
    contract_code = f"HD-{room.room_number}-{timestamp_str}"

    rent_amount = (
        contract_in.monthly_rent
        if contract_in.monthly_rent is not None
        else room.price
    )

    contract = Contract(
        contract_code=contract_code,
        room_id=room.id,
        tenant_id=tenant.id,
        start_date=contract_in.start_date,
        end_date=contract_in.end_date,
        deposit_amount=contract_in.deposit_amount,
        monthly_rent=rent_amount,
        electricity_rate=contract_in.electricity_rate,
        water_rate=contract_in.water_rate,
        service_fee=contract_in.service_fee,
        status="ACTIVE",
        notes=contract_in.notes,
    )
    db.add(contract)

    # 5. Update room status to RENTED
    room.status = "RENTED"

    db.commit()
    db.refresh(contract)
    return contract


def terminate_contract(db: Session, contract_id: int, notes: Optional[str] = None) -> Contract:
    """
    Terminate an active contract.
    - Sets contract status to 'TERMINATED'.
    - Releases room back to 'AVAILABLE'.
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

    # Release room
    if contract.room:
        contract.room.status = "AVAILABLE"

    db.commit()
    db.refresh(contract)
    return contract

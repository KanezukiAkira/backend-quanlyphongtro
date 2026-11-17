from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.contract import Contract
from app.schemas.tenant import TenantResponse


def get_tenant_by_id(db: Session, tenant_id: int) -> Optional[User]:
    """Retrieve tenant user by ID."""
    return db.query(User).filter(User.id == tenant_id, User.role == "TENANT").first()


def enrich_tenant_response(db: Session, tenant: User) -> TenantResponse:
    """Enrich a User object into TenantResponse with active room info if available."""
    active_contract = (
        db.query(Contract)
        .filter(Contract.tenant_id == tenant.id, Contract.status == "ACTIVE")
        .first()
    )
    current_room_id = active_contract.room_id if active_contract else None
    current_room_number = active_contract.room.room_number if active_contract and active_contract.room else None

    return TenantResponse(
        id=tenant.id,
        username=tenant.username,
        full_name=tenant.full_name,
        phone=tenant.phone,
        email=tenant.email,
        role=tenant.role,
        created_at=tenant.created_at,
        current_room_id=current_room_id,
        current_room_number=current_room_number,
    )


def get_all_tenants(db: Session, skip: int = 0, limit: int = 100) -> List[TenantResponse]:
    """Retrieve all tenant accounts with their room assignment info."""
    tenants = (
        db.query(User)
        .filter(User.role == "TENANT")
        .order_by(User.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [enrich_tenant_response(db, t) for t in tenants]


def get_available_tenants(db: Session) -> List[TenantResponse]:
    """
    Retrieve tenants who do NOT currently have an ACTIVE contract.
    Useful for selecting an eligible tenant when creating a new rental contract.
    """
    active_tenant_ids_query = (
        db.query(Contract.tenant_id)
        .filter(Contract.status == "ACTIVE")
    )
    tenants = (
        db.query(User)
        .filter(User.role == "TENANT", User.id.not_in(active_tenant_ids_query))
        .order_by(User.full_name.asc())
        .all()
    )
    return [enrich_tenant_response(db, t) for t in tenants]

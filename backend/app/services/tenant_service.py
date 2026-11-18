from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.archived_tenant import ArchivedTenant
from app.models.contract import Contract
from app.models.room import Room
from app.models.user import User
from app.schemas.tenant import ArchivedTenantResponse, TenantResponse
from app.services.cron_service import cleanup_expired_archived_tenants


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
    current_room_id = active_contract.room_id if active_contract else tenant.room_id
    current_room_number = None
    if active_contract and active_contract.room:
        current_room_number = active_contract.room.room_number
    elif tenant.room_id:
        room = db.query(Room).filter(Room.id == tenant.room_id).first()
        current_room_number = room.room_number if room else tenant.username

    return TenantResponse(
        id=tenant.id,
        username=tenant.username,
        full_name=tenant.full_name,
        gender=tenant.gender,
        birth_date=tenant.birth_date,
        phone=tenant.phone,
        email=tenant.email,
        cccd=tenant.cccd,
        hometown=tenant.hometown,
        role=tenant.role,
        room_id=tenant.room_id,
        is_profile_completed=bool(tenant.is_profile_completed),
        token_version=tenant.token_version or 1,
        created_at=tenant.created_at,
        current_room_id=current_room_id,
        current_room_number=current_room_number,
    )


def get_all_tenants(db: Session, skip: int = 0, limit: int = 100) -> List[TenantResponse]:
    """Retrieve all tenant accounts with their room assignment and profile info."""
    tenants = (
        db.query(User)
        .filter(User.role == "TENANT")
        .order_by(User.username.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [enrich_tenant_response(db, t) for t in tenants]


def get_available_tenants(db: Session) -> List[TenantResponse]:
    """
    Retrieve tenants who do NOT currently have an ACTIVE contract.
    """
    active_tenant_ids_query = (
        db.query(Contract.tenant_id)
        .filter(Contract.status == "ACTIVE")
    )
    tenants = (
        db.query(User)
        .filter(User.role == "TENANT", User.id.not_in(active_tenant_ids_query))
        .order_by(User.username.asc())
        .all()
    )
    return [enrich_tenant_response(db, t) for t in tenants]


def get_archived_tenants(db: Session) -> List[ArchivedTenantResponse]:
    """
    Lấy danh sách khách thuê cũ đang trong mục Lưu trữ tạm (Archived - giữ 30 ngày).
    Tự động kích hoạt Cronjob xóa các hồ sơ đã quá 30 ngày trước khi trả về.
    """
    cleanup_expired_archived_tenants(db)
    now = datetime.now(timezone.utc)
    records = (
        db.query(ArchivedTenant)
        .order_by(ArchivedTenant.deleted_at.desc(), ArchivedTenant.id.desc())
        .all()
    )

    result = []
    for rec in records:
        exp = rec.expire_at
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        days_left = max(0, (exp - now).days) if exp else 0
        result.append(
            ArchivedTenantResponse(
                id=rec.id,
                original_user_id=rec.original_user_id,
                room_id=rec.room_id,
                room_number=rec.room_number,
                username=rec.username,
                full_name=rec.full_name,
                gender=rec.gender,
                birth_date=rec.birth_date,
                phone=rec.phone,
                email=rec.email,
                cccd=rec.cccd,
                hometown=rec.hometown,
                contract_code=rec.contract_code,
                check_in_date=rec.check_in_date,
                check_out_date=rec.check_out_date,
                checkout_reason=rec.checkout_reason,
                status=rec.status,
                deleted_at=rec.deleted_at,
                expire_at=rec.expire_at,
                days_remaining=days_left,
            )
        )
    return result


def delete_archived_tenant(db: Session, archived_id: int) -> bool:
    rec = db.query(ArchivedTenant).filter(ArchivedTenant.id == archived_id).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hồ sơ lưu trữ tạm",
        )
    db.delete(rec)
    db.commit()
    return True

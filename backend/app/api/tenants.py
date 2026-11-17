from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_landlord
from app.models.user import User
from app.schemas.tenant import TenantResponse
from app.services.tenant_service import (
    get_all_tenants,
    get_available_tenants,
    get_tenant_by_id,
    enrich_tenant_response,
)

router = APIRouter()


@router.get("", response_model=List[TenantResponse])
@router.get("/", response_model=List[TenantResponse], include_in_schema=False)
def list_tenants(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Lấy danh sách tất cả khách thuê (chỉ chủ trọ)."""
    return get_all_tenants(db, skip=skip, limit=limit)


@router.get("/available", response_model=List[TenantResponse])
def list_available_tenants(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Lấy danh sách khách thuê chưa có hợp đồng thuê phòng hiệu lực
    (dùng để tạo hợp đồng mới).
    """
    return get_available_tenants(db)


@router.get("/{id}", response_model=TenantResponse)
def get_tenant(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Xem chi tiết khách thuê theo ID (chỉ chủ trọ)."""
    tenant = get_tenant_by_id(db, id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách thuê có ID {id}",
        )
    return enrich_tenant_response(db, tenant)

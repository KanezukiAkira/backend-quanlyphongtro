from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_landlord
from app.models.user import User
from app.schemas.tenant import ArchivedTenantResponse, TenantResponse
from app.services.cron_service import cleanup_expired_archived_tenants
from app.services.tenant_service import (
    delete_archived_tenant,
    enrich_tenant_response,
    get_all_tenants,
    get_archived_tenants,
    get_available_tenants,
    get_tenant_by_id,
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
    """Lấy danh sách tất cả tài khoản phòng / khách thuê (chỉ chủ trọ)."""
    return get_all_tenants(db, skip=skip, limit=limit)


@router.get("/available", response_model=List[TenantResponse])
def list_available_tenants(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Lấy danh sách tài khoản khách thuê chưa có hợp đồng thuê phòng hiệu lực."""
    return get_available_tenants(db)


@router.get("/archived", response_model=List[ArchivedTenantResponse])
def list_archived(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Lấy danh sách hồ sơ khách thuê cũ đang trong mục Lưu trữ tạm (Archived - giữ 30 ngày sau khi trả phòng).
    Tự động xóa các hồ sơ đã quá hạn 30 ngày.
    """
    return get_archived_tenants(db)


@router.post("/cleanup-archived")
def trigger_cleanup_archived(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Kích hoạt Cronjob xóa vĩnh viễn các hồ sơ khách cũ đã lưu trữ quá 30 ngày."""
    deleted = cleanup_expired_archived_tenants(db)
    return {
        "message": f"Đã chạy Cronjob dọn dẹp kho lưu trữ tạm: xóa vĩnh viễn {deleted} hồ sơ quá 30 ngày.",
        "deleted_count": deleted,
    }


@router.delete("/archived/{archived_id}")
def remove_archived(
    archived_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Xóa vĩnh viễn một hồ sơ trong mục lưu trữ tạm."""
    delete_archived_tenant(db, archived_id)
    return {"message": "Đã xóa vĩnh viễn hồ sơ khách thuê lưu trữ", "id": archived_id}


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

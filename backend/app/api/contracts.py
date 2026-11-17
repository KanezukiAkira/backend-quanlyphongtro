from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_landlord
from app.models.user import User
from app.schemas.contract import ContractCreate, ContractResponse
from app.services.contract_service import (
    get_contracts,
    get_contract_by_id,
    get_active_contracts,
    get_tenant_contract,
    create_contract,
    terminate_contract,
)

router = APIRouter()


class ContractTerminateRequest(BaseModel):
    notes: Optional[str] = None


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ContractResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def make_contract(
    contract_in: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Tạo hợp đồng thuê phòng mới (chỉ chủ trọ).
    Tự động chuyển trạng thái phòng sang 'RENTED'.
    """
    return create_contract(db, contract_in)


@router.get("", response_model=List[ContractResponse])
@router.get("/", response_model=List[ContractResponse], include_in_schema=False)
def list_contracts(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái hợp đồng: ACTIVE, EXPIRED, TERMINATED"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Lấy danh sách tất cả các hợp đồng thuê (chỉ chủ trọ)."""
    return get_contracts(db, status=status, skip=skip, limit=limit)


@router.get("/active", response_model=List[ContractResponse])
def list_active_contracts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Lấy danh sách các hợp đồng đang có hiệu lực (chỉ chủ trọ)."""
    return get_active_contracts(db)


@router.get("/my-contract", response_model=ContractResponse)
def get_my_contract(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy thông tin hợp đồng của khách thuê đang đăng nhập."""
    contract = get_tenant_contract(db, current_user.id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hợp đồng thuê phòng nào của bạn",
        )
    return contract


@router.get("/{id}", response_model=ContractResponse)
def get_contract(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xem chi tiết hợp đồng theo ID."""
    contract = get_contract_by_id(db, id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hợp đồng có ID {id}",
        )
    if current_user.role == "TENANT" and contract.tenant_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem thông tin hợp đồng này",
        )
    return contract


@router.put("/{id}/terminate", response_model=ContractResponse)
def end_contract(
    id: int,
    req: Optional[ContractTerminateRequest] = None,
    notes: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Thanh lý / kết thúc hợp đồng thuê (chỉ chủ trọ).
    Tự động cập nhật phòng về trạng thái 'AVAILABLE'.
    """
    note_content = req.notes if (req and req.notes) else notes
    return terminate_contract(db, contract_id=id, notes=note_content)

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_landlord
from app.models.user import User
from app.schemas.contract import ContractCreate, ContractResponse
from app.services.contract_service import (
    create_contract,
    get_active_contracts,
    get_contract_by_id,
    get_contract_by_room,
    get_contracts,
    get_tenant_contract,
    terminate_contract,
)
from app.services.pdf_email_service import generate_contract_pdf

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
    Tạo hợp đồng thuê phòng mới theo mẫu chuẩn pháp luật Việt Nam (chỉ chủ trọ).
    Tự động chuyển trạng thái phòng sang 'RENTED'.
    """
    return create_contract(db, contract_in)


@router.get("", response_model=List[ContractResponse])
@router.get("/", response_model=List[ContractResponse], include_in_schema=False)
def list_contracts(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái hợp đồng: ACTIVE, EXPIRED, TERMINATED"),
    room_id: Optional[int] = Query(None, description="Lọc theo ID phòng"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """Lấy danh sách tất cả các hợp đồng thuê (chỉ chủ trọ)."""
    return get_contracts(db, status=status, room_id=room_id, skip=skip, limit=limit)


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
    """Lấy thông tin hợp đồng của khách thuê / tài khoản phòng đang đăng nhập."""
    contract = get_tenant_contract(db, current_user.id, room_id=current_user.room_id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hợp đồng thuê phòng nào của bạn",
        )
    return contract


@router.get("/by-room/{room_id}", response_model=ContractResponse)
def get_room_contract(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy hợp đồng hiện tại của một phòng cụ thể."""
    if current_user.role == "TENANT" and current_user.room_id and current_user.room_id != room_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem hợp đồng của phòng khác",
        )
    contract = get_contract_by_room(db, room_id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Phòng ID {room_id} hiện chưa có hợp đồng thuê nhà",
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
    if current_user.role == "TENANT":
        if contract.tenant_id != current_user.id and contract.room_id != current_user.room_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xem thông tin hợp đồng này",
            )
    return contract


@router.get("/{id}/pdf")
def download_contract_pdf(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Xuất / Tải xuống Hợp đồng thuê trọ chuẩn pháp luật Việt Nam (File PDF).
    Có Quốc hiệu, Tiêu ngữ, căn cứ Bộ luật Dân sự & Luật Nhà ở Việt Nam, Bên A, Bên B, chữ ký.
    """
    contract = get_contract_by_id(db, id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hợp đồng",
        )
    if current_user.role == "TENANT":
        if contract.tenant_id != current_user.id and contract.room_id != current_user.room_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền tải hợp đồng của phòng khác",
            )
    pdf_bytes = generate_contract_pdf(contract)
    filename = f"Hop-Dong-Thue-Phong-{contract.contract_code}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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

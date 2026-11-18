from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_landlord
from app.models.user import User
from app.schemas.auth import (
    ProfileUpdateRequest,
    Token,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth_service import (
    login_user,
    register_tenant,
    revoke_all_sessions,
    update_user_profile,
)

router = APIRouter()


class RevokeSessionRequest(BaseModel):
    new_password: Optional[str] = None


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    """Đăng ký tài khoản khách thuê mới."""
    return register_tenant(db, user_in)


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Đăng nhập hệ thống (Chủ trọ: admin hoặc Tài khoản Phòng: 1.1 -> 3.5).
    Hỗ trợ cả JSON body lẫn Form Data.
    """
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên đăng nhập và mật khẩu không được để trống",
            )
        login_in = UserLogin(username=str(username), password=str(password))
    else:
        try:
            body = await request.json()
            login_in = UserLogin(**body)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Dữ liệu đăng nhập không hợp lệ. Vui lòng gửi JSON gồm username và password.",
            )
    return login_user(db, login_in)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Lấy thông tin tài khoản đang đăng nhập."""
    return current_user


@router.put("/profile", response_model=UserResponse)
def update_profile(
    profile_in: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Khai báo thông tin hồ sơ lần đầu hoặc cập nhật thông tin cá nhân của Khách thuê (Tài khoản Phòng):
    Họ tên, Giới tính, Ngày sinh, SĐT, Gmail, CCCD, Quê quán.
    """
    return update_user_profile(db, current_user, profile_in)


@router.post("/revoke-sessions/{user_id}", response_model=UserResponse)
def revoke_sessions_endpoint(
    user_id: int,
    req: Optional[RevokeSessionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_landlord),
):
    """
    Chủ trọ thu hồi toàn bộ thiết bị đang đăng nhập vào một tài khoản phòng (Invalidate JWT token_version)
    và đặt lại mật khẩu mới.
    """
    new_pwd = req.new_password if req else None
    return revoke_all_sessions(db, user_id=user_id, new_password=new_pwd)

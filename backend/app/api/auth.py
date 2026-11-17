from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, UserResponse, Token
from app.services.auth_service import register_tenant, login_user

router = APIRouter()


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
    Đăng nhập hệ thống (chủ trọ hoặc khách thuê).
    Hỗ trợ cả JSON body lẫn Form Data (Swagger UI / OAuth2).
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

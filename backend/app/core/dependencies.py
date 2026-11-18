from typing import Optional
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    token_query: Optional[str] = Query(None, alias="token", include_in_schema=False),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency to retrieve the authenticated user from JWT token.
    Also validates token_version to support instant multi-device session revocation.
    """
    actual_token = token or token_query
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not actual_token:
        raise credentials_exception

    payload = decode_access_token(actual_token)
    if payload is None:
        raise credentials_exception

    username: Optional[str] = payload.get("sub")
    if username is None:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception

    # Kiểm tra token_version để thu hồi phiên đăng nhập khi Chủ trọ bấm "Khách trả phòng / Reset tài khoản"
    token_ver = payload.get("token_version")
    if token_ver is not None and user.token_version is not None:
        if int(token_ver) != int(user.token_version):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên đăng nhập của thiết bị này đã bị thu hồi bởi Chủ trọ. Vui lòng đăng nhập lại.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return user


def require_landlord(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency enforcing that the current user has the LANDLORD role."""
    if current_user.role != "LANDLORD":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Thao tác không được phép. Yêu cầu quyền Chủ trọ (Admin).",
        )
    return current_user

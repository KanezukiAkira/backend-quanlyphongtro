from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Retrieve user by primary key ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Retrieve user by username."""
    return db.query(User).filter(User.username == username).first()


def register_tenant(db: Session, user_in: UserRegister) -> User:
    """
    Register a new tenant account.
    Enforces uniqueness of username and assigns role 'TENANT'.
    Note: No CCCD requirement.
    """
    existing_user = get_user_by_username(db, user_in.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên đăng nhập đã tồn tại trên hệ thống",
        )

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        username=user_in.username,
        password_hash=hashed_pw,
        full_name=user_in.full_name,
        phone=user_in.phone,
        email=user_in.email,
        role="TENANT",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def login_user(db: Session, login_in: UserLogin) -> dict:
    """
    Authenticate user credentials and issue a JWT access token.
    """
    user = get_user_by_username(db, login_in.username)
    if not user or not verify_password(login_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }

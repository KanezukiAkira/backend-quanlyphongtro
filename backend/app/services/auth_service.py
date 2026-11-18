from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User
from app.models.room import Room
from app.schemas.auth import UserRegister, UserLogin, ProfileUpdateRequest
from app.services.notification_service import create_notification


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Retrieve user by primary key ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Retrieve user by username."""
    return db.query(User).filter(User.username == username).first()


def register_tenant(db: Session, user_in: UserRegister) -> User:
    """Register a new tenant account."""
    existing_user = get_user_by_username(db, user_in.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên đăng nhập đã tồn tại trên hệ thống",
        )

    room = db.query(Room).filter(Room.room_number == user_in.username).first()

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        username=user_in.username,
        password_hash=hashed_pw,
        full_name=user_in.full_name,
        gender=user_in.gender,
        birth_date=user_in.birth_date,
        phone=user_in.phone,
        email=user_in.email,
        cccd=user_in.cccd,
        hometown=user_in.hometown,
        role="TENANT",
        room_id=room.id if room else None,
        is_profile_completed=bool(user_in.cccd and user_in.phone),
        token_version=1,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def login_user(db: Session, login_in: UserLogin) -> dict:
    """
    Authenticate user credentials and issue a JWT access token containing token_version.
    """
    user = get_user_by_username(db, login_in.username)
    if not user or not verify_password(login_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role,
            "user_id": user.id,
            "token_version": user.token_version or 1,
        }
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


def update_user_profile(db: Session, current_user: User, profile_in: ProfileUpdateRequest) -> User:
    """
    Khai báo / Cập nhật hồ sơ người thuê lần đầu hoặc chỉnh sửa thông tin cá nhân:
    Họ tên, Giới tính, Ngày sinh, SĐT, Gmail, CCCD, Quê quán.
    """
    current_user.full_name = profile_in.full_name.strip()
    current_user.gender = profile_in.gender
    current_user.birth_date = profile_in.birth_date
    current_user.phone = profile_in.phone.strip()
    current_user.email = profile_in.email.strip()
    current_user.cccd = profile_in.cccd.strip()
    current_user.hometown = profile_in.hometown.strip()
    current_user.is_profile_completed = True

    if profile_in.new_password:
        current_user.password_hash = get_password_hash(profile_in.new_password)

    # Nếu tài khoản phòng đang ở trạng thái AVAILABLE khi khách vào khai báo hồ sơ -> chuyển sang RENTED
    if current_user.room_id:
        room = db.query(Room).filter(Room.id == current_user.room_id).first()
        if room and room.status == "AVAILABLE":
            room.status = "RENTED"

    db.commit()
    db.refresh(current_user)

    room_label = current_user.username
    create_notification(
        db,
        recipient_role="LANDLORD",
        room_id=current_user.room_id,
        title=f"Phòng {room_label} vừa cập nhật hồ sơ khách thuê",
        message=(
            f"Khách thuê {current_user.full_name} (CCCD: {current_user.cccd}, SĐT: {current_user.phone}, "
            f"Quê quán: {current_user.hometown}) đã hoàn tất khai báo thông tin tại Phòng {room_label}."
        ),
        notif_type="SYSTEM",
        related_id=current_user.id,
    )
    return current_user


def revoke_all_sessions(db: Session, user_id: int, new_password: Optional[str] = None) -> User:
    """
    Thu hồi toàn bộ các thiết bị đang đăng nhập vào tài khoản (Invalidate JWT token_version)
    và đặt lại mật khẩu mới nếu có.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản",
        )
    user.token_version = (user.token_version or 1) + 1
    if new_password:
        user.password_hash = get_password_hash(new_password)
    db.commit()
    db.refresh(user)
    return user

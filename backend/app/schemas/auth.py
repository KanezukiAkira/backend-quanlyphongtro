from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserRegister(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=4, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=255)
    gender: Optional[str] = Field(None, max_length=30)
    birth_date: Optional[date] = None
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    cccd: Optional[str] = Field(None, max_length=50)
    hometown: Optional[str] = Field(None, max_length=255)


class UserLogin(BaseModel):
    username: str
    password: str


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    gender: Optional[str] = Field("Nam", max_length=30)
    birth_date: Optional[date] = None
    phone: str = Field(..., min_length=8, max_length=50)
    email: str = Field(..., min_length=3, max_length=255)
    cccd: str = Field(..., min_length=9, max_length=50)
    hometown: str = Field(..., min_length=2, max_length=255)
    new_password: Optional[str] = Field(None, min_length=4, max_length=100)


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    cccd: Optional[str] = None
    hometown: Optional[str] = None
    role: str
    room_id: Optional[int] = None
    is_profile_completed: bool = False
    token_version: int = 1
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[UserResponse] = None


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    user_id: Optional[int] = None
    token_version: Optional[int] = None

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class RoomBase(BaseModel):
    room_number: str = Field(..., min_length=1, max_length=50)
    price: float = Field(0.0, ge=0.0)
    area: Optional[float] = Field(None, ge=0.0)
    max_occupants: int = Field(2, ge=1)
    status: str = Field("AVAILABLE", max_length=50)  # AVAILABLE, RENTED, MAINTENANCE
    description: Optional[str] = None


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    room_number: Optional[str] = Field(None, min_length=1, max_length=50)
    price: Optional[float] = Field(None, ge=0.0)
    area: Optional[float] = Field(None, ge=0.0)
    max_occupants: Optional[int] = Field(None, ge=1)
    status: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class RoomResponse(RoomBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

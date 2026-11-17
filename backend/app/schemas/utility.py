from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UtilityReadingCreate(BaseModel):
    room_id: int
    month_year: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="Format: YYYY-MM")
    recorded_date: Optional[date] = None
    old_electricity: Optional[float] = Field(None, ge=0.0)
    new_electricity: float = Field(..., ge=0.0)
    old_water: Optional[float] = Field(None, ge=0.0)
    new_water: float = Field(..., ge=0.0)
    recorded_by: Optional[int] = None


class UtilityReadingResponse(BaseModel):
    id: int
    room_id: int
    month_year: str
    recorded_date: date
    old_electricity: float
    new_electricity: float
    electricity_usage: Optional[float] = None
    old_water: float
    new_water: float
    water_usage: Optional[float] = None
    recorded_by: Optional[int] = None
    created_at: Optional[datetime] = None
    room_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

from datetime import date
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.utility_reading import UtilityReading
from app.models.room import Room
from app.schemas.utility import UtilityReadingCreate, UtilityReadingResponse


def enrich_reading_response(reading: UtilityReading) -> UtilityReadingResponse:
    """Format UtilityReading model into UtilityReadingResponse with computed usages."""
    elec_usage = max(0.0, reading.new_electricity - reading.old_electricity)
    water_usage = max(0.0, reading.new_water - reading.old_water)
    room_number = reading.room.room_number if reading.room else None

    return UtilityReadingResponse(
        id=reading.id,
        room_id=reading.room_id,
        month_year=reading.month_year,
        recorded_date=reading.recorded_date,
        old_electricity=reading.old_electricity,
        new_electricity=reading.new_electricity,
        electricity_usage=elec_usage,
        old_water=reading.old_water,
        new_water=reading.new_water,
        water_usage=water_usage,
        recorded_by=reading.recorded_by,
        created_at=reading.created_at,
        room_number=room_number,
    )


def get_last_reading(db: Session, room_id: int) -> Optional[UtilityReading]:
    """Retrieve the most recent utility reading for a room."""
    return (
        db.query(UtilityReading)
        .filter(UtilityReading.room_id == room_id)
        .order_by(UtilityReading.recorded_date.desc(), UtilityReading.id.desc())
        .first()
    )


def get_readings(
    db: Session,
    room_id: Optional[int] = None,
    month_year: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[UtilityReadingResponse]:
    """Retrieve list of utility readings with optional filters."""
    query = db.query(UtilityReading)
    if room_id:
        query = query.filter(UtilityReading.room_id == room_id)
    if month_year:
        query = query.filter(UtilityReading.month_year == month_year)

    readings = (
        query.order_by(UtilityReading.recorded_date.desc(), UtilityReading.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [enrich_reading_response(r) for r in readings]


def get_reading_by_id(db: Session, reading_id: int) -> Optional[UtilityReadingResponse]:
    """Retrieve utility reading by ID."""
    reading = db.query(UtilityReading).filter(UtilityReading.id == reading_id).first()
    if not reading:
        return None
    return enrich_reading_response(reading)


def record_reading(
    db: Session,
    reading_in: UtilityReadingCreate,
    recorded_by: Optional[int] = None
) -> UtilityReadingResponse:
    """
    Record or update electricity & water meter readings for a room and month.
    - Automatically pulls old readings from previous records if omitted.
    - Validates new readings are not less than old readings.
    """
    room = db.query(Room).filter(Room.id == reading_in.room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phòng có ID {reading_in.room_id}",
        )

    last_record = get_last_reading(db, reading_in.room_id)

    old_elec = (
        reading_in.old_electricity
        if reading_in.old_electricity is not None
        else (last_record.new_electricity if last_record else 0.0)
    )
    old_water = (
        reading_in.old_water
        if reading_in.old_water is not None
        else (last_record.new_water if last_record else 0.0)
    )

    if reading_in.new_electricity < old_elec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ số điện mới ({reading_in.new_electricity}) không thể nhỏ hơn chỉ số cũ ({old_elec})",
        )

    if reading_in.new_water < old_water:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ số nước mới ({reading_in.new_water}) không thể nhỏ hơn chỉ số cũ ({old_water})",
        )

    rec_date = reading_in.recorded_date or date.today()
    rec_by = reading_in.recorded_by or recorded_by

    # Check if a reading already exists for this room and month_year
    existing = (
        db.query(UtilityReading)
        .filter(
            UtilityReading.room_id == reading_in.room_id,
            UtilityReading.month_year == reading_in.month_year,
        )
        .first()
    )

    if existing:
        existing.recorded_date = rec_date
        existing.old_electricity = old_elec
        existing.new_electricity = reading_in.new_electricity
        existing.old_water = old_water
        existing.new_water = reading_in.new_water
        if rec_by:
            existing.recorded_by = rec_by
        db.commit()
        db.refresh(existing)
        return enrich_reading_response(existing)

    reading = UtilityReading(
        room_id=reading_in.room_id,
        month_year=reading_in.month_year,
        recorded_date=rec_date,
        old_electricity=old_elec,
        new_electricity=reading_in.new_electricity,
        old_water=old_water,
        new_water=reading_in.new_water,
        recorded_by=rec_by,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return enrich_reading_response(reading)

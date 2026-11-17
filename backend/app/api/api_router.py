from fastapi import APIRouter
from app.api import auth, rooms, tenants, contracts, utilities, invoices, stats

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
api_router.include_router(utilities.router, prefix="/utilities", tags=["utilities"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])

from fastapi import APIRouter
from app.api import (
    auth,
    contracts,
    feedbacks,
    invoices,
    notifications,
    rooms,
    stats,
    tenants,
    utilities,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["1. Auth & Account Service"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["2. Room Service"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["3. Tenant & Archive Service"])
api_router.include_router(contracts.router, prefix="/contracts", tags=["4. Contract Service (Vietnamese Law)"])
api_router.include_router(utilities.router, prefix="/utilities", tags=["5. Utility Meter Service"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["5. Billing & Payment Service"])
api_router.include_router(feedbacks.router, prefix="/feedbacks", tags=["6. Feedback Service"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["6. Notification Service (Toast & Bell)"])
api_router.include_router(stats.router, prefix="/stats", tags=["7. Analytics, Debt & Cronjob Service"])

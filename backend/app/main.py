import asyncio
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.core.database import SessionLocal
from app.core.init_db import init_db
from app.api.api_router import api_router
from app.services.cron_service import run_all_cronjobs

app = FastAPI(
    title="Hệ Thống Quản Lý Nhà Trọ & Thanh Toán Tiền Phòng API",
    description=(
        "Backend Modular Service Architecture (FastAPI + MySQL): "
        "1. Auth & Account Service | 2. Room Service | 3. Tenant & 30-Day Archive Service | "
        "4. Vietnamese Legal Contract Service | 5. Billing, Payment & Debt Service | "
        "6. Feedback & Real-time Notification Service (Toast 10s + Bell)."
    ),
    version="2.0.0",
)

# CORS allow all
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _periodic_cron_worker():
    """Background Cronjob running periodically to purge >30d archived tenants & mark overdue bills after day 15."""
    while True:
        try:
            db = SessionLocal()
            try:
                run_all_cronjobs(db)
            finally:
                db.close()
        except Exception:
            pass
        await asyncio.sleep(3600)


@app.on_event("startup")
async def on_startup():
    init_db()
    asyncio.create_task(_periodic_cron_worker())


# Include all API endpoints under /api
app.include_router(api_router, prefix="/api")

# Serve Frontend HTML/CSS/JS directly at /app and /frontend
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


@app.get("/app", include_in_schema=False)
def serve_web_portal():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Frontend index.html not found"}


@app.get("/styles.css", include_in_schema=False)
def serve_styles_css():
    css_file = FRONTEND_DIR / "styles.css"
    return FileResponse(str(css_file), media_type="text/css")


@app.get("/app.js", include_in_schema=False)
def serve_app_js():
    js_file = FRONTEND_DIR / "app.js"
    return FileResponse(str(js_file), media_type="application/javascript")


@app.get("/")
def root():
    return {
        "message": "Hệ Thống Quản Lý Nhà Trọ và Thanh Toán Tiền Phòng API đang hoạt động",
        "portal_url": "http://127.0.0.1:8000/app",
        "docs": "/docs",
        "status": "online",
    }

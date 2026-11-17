from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.init_db import init_db
from app.api.api_router import api_router

app = FastAPI(
    title="Hệ Thống Quản Lý Phòng Trọ API",
    description="Backend API cho hệ thống quản lý phòng trọ: quản lý phòng, khách thuê, hợp đồng thuê phòng, chỉ số điện nước, tính toán hóa đơn tự động và thống kê doanh thu.",
    version="1.0.0",
)

# CORS allow all
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# Include all API endpoints under /api
app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "Hệ Thống Quản Lý Phòng Trọ API đang hoạt động",
        "docs": "/docs",
        "status": "online",
    }

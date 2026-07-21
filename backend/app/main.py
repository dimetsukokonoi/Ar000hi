"""
Arooohi Backend — FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.database import init_db
from app.routes.auth import router as auth_router
from app.routes.drivers import router as drivers_router
from app.routes.tracking import router as tracking_router
from app.routes.sos import router as sos_router
from app.routes.complaints import router as complaints_router

# Initialize database on startup
init_db()

app = FastAPI(
    title="Arooohi API",
    description="Student-to-student ride-sharing network — Backend API",
    version="1.0.0",
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Register routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(drivers_router, prefix="/api/drivers", tags=["Driver Verification"])
app.include_router(tracking_router, prefix="/api/tracking", tags=["GPS Tracking"])
app.include_router(sos_router, prefix="/api/sos", tags=["SOS Alerts"])
app.include_router(complaints_router, prefix="/api/complaints", tags=["Complaints"])


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Arooohi API", "version": "1.0.0"}

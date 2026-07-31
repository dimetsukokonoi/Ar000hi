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

# Ornab: Trusted Contacts (#12), Rides core (#5 splitter), Surge (#13), Chat (#15), Eco (#20)
from app.routes.contacts import router as contacts_router
from app.routes.rides import router as rides_router
from app.routes.surge import router as surge_router
from app.routes.chat import router as chat_router
from app.routes.eco import router as eco_router

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

# Ornab's modules
app.include_router(contacts_router, prefix="/api/contacts", tags=["Trusted Contacts"])
app.include_router(rides_router, prefix="/api/rides", tags=["Rides"])
app.include_router(surge_router, prefix="/api/surge", tags=["Peak Hour Surge"])
app.include_router(chat_router, prefix="/ws", tags=["Ride Chat"])
app.include_router(eco_router, prefix="/api/eco", tags=["Eco Tracker"])


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Arooohi API", "version": "1.0.0"}

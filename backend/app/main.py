"""
Arooohi Backend — FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.models.database import init_db
from app.models.errors import DomainError
from app.controllers.errors import domain_error_handler
from app.controllers.health import router as health_router
from app.controllers.auth import router as auth_router
from app.controllers.drivers import router as drivers_router
from app.controllers.tracking import router as tracking_router
from app.controllers.sos import router as sos_router
from app.controllers.complaints import router as complaints_router

# Ornab: Trusted Contacts (#12), Rides core (#5 splitter), Surge (#13), Chat (#15), Eco (#20)
from app.controllers.contacts import router as contacts_router
from app.controllers.rides import router as rides_router
from app.controllers.surge import router as surge_router
from app.controllers.chat import router as chat_router
from app.controllers.eco import router as eco_router

# Feature 9: Wallet & bKash Integration
from app.controllers.wallet import router as wallet_router
from app.controllers.bkash_checkout import router as bkash_checkout_router

# Feature 16: Driver Earnings Dashboard
from app.controllers.earnings import router as earnings_router

# Feature 10: Ride History & Receipt Log
from app.controllers.history import router as history_router

# Feature 7: Driver Rating & Review
from app.controllers.reviews import router as reviews_router

# Initialize database on startup
init_db()

app = FastAPI(
    title="Arooohi API",
    description="Student-to-student ride-sharing network — Backend API",
    version="1.0.0",
)
app.add_exception_handler(DomainError, domain_error_handler)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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

# Wallet (Feature 9)
app.include_router(wallet_router, prefix="/api/wallet", tags=["Wallet & bKash"])
app.include_router(earnings_router, prefix="/api/earnings", tags=["Driver Earnings"])
app.include_router(history_router, prefix="/api/history", tags=["Ride History & Receipts"])
app.include_router(reviews_router, prefix="/api/reviews", tags=["Driver Rating & Review"])

# The SIMULATED bKash gateway page. Mounted only in demo mode — in production the
# browser would be redirected to bKash's own hosted checkout instead. Deliberately
# not under /api and deliberately unauthenticated: it stands in for a third party.
if os.getenv("DEMO_MODE", "1") == "1":
    app.include_router(bkash_checkout_router, prefix="/bkash", tags=["bKash (simulated)"])


app.include_router(health_router)

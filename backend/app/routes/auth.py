"""
Arooohi Backend — Auth Routes
Feature 1: BRACU Student Verification  (Sami's Sprint-1 module; improved by Ornab's agent pass)
Improvements in this pass:
- DEMO_MODE gating: OTP is returned in the response only when DEMO_MODE=1 (default),
  matching how the demo frontend surfaces the "Demo OTP". In production the OTP is
  logged server-side only (email delivery would replace this).
- In-memory rate limiting on login + OTP verify (per email + IP) to blunt brute force.
- resend_otp now uses a Pydantic model instead of a raw dict.
- Password minimum length enforced server-side (matches the frontend minLength=6).
"""
import uuid
import random
import time
import threading
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.auth import hash_password, verify_password, create_access_token, get_current_user_id

router = APIRouter()

BRACU_DOMAIN = "g.bracu.ac.bd"
DEMO_MODE = __import__("os").getenv("DEMO_MODE", "1") == "1"

# ---- Simple in-memory rate limiter (single-process demo) ----
# Structure: key -> list of (attempt_ts). MAX_ATTEMPTS in WINDOW_S then lockout.
_MAX_ATTEMPTS = 5
_WINDOW_S = 300
_LOCKOUT_S = 300
_rate_attempts: dict[str, list[float]] = {}
_rate_lock = threading.Lock()


def _rate_key(request: Request, email: str, scope: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{scope}|{client}|{email.lower()}"


def _check_rate(key: str) -> None:
    now = time.time()
    with _rate_lock:
        stamps = [t for t in _rate_attempts.get(key, []) if now - t < _WINDOW_S]
        # If we already hit the cap, enforce lockout until the oldest attempt ages out.
        if len(stamps) >= _MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Please wait a few minutes and try again.",
            )
        _rate_attempts[key] = stamps


def _record_rate(key: str) -> None:
    now = time.time()
    with _rate_lock:
        stamps = [t for t in _rate_attempts.get(key, []) if now - t < _WINDOW_S]
        stamps.append(now)
        _rate_attempts[key] = stamps


def _otp_hint(code: str):
    """Return the OTP for the demo frontend when DEMO_MODE is on; otherwise omit."""
    if DEMO_MODE:
        return {"otp_hint": code}
    return {}


class RegisterRequest(BaseModel):
    name: str
    email: str
    phone: str
    password: str
    gender: str  # male, female, other


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyOTPRequest(BaseModel):
    email: str
    code: str


class ResendOTPRequest(BaseModel):
    email: str


@router.post("/register")
def register(body: RegisterRequest):
    """Register a new student — BRACU email only.

    Notes:
    - This module remains part of the shared Sprint-1 authentication foundation.
    - Ornab's Sprint-2 work depends on the verified BRACU identity gate.
    """
    email = body.email.strip().lower()
    phone = body.phone.strip()

    # Validate BRACU email domain
    if not email.endswith(f"@{BRACU_DOMAIN}"):
        raise HTTPException(
            status_code=400,
            detail=f"Only @{BRACU_DOMAIN} emails are allowed. Please use your BRACU student email."
        )

    if body.gender not in ("male", "female", "other"):
        raise HTTPException(status_code=400, detail="Gender must be male, female, or other")

    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    conn = get_db()

    # Check if email already exists
    existing = conn.execute("SELECT id FROM users WHERE bracu_email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    # Create user
    user_id = str(uuid.uuid4())
    hashed = hash_password(body.password)

    conn.execute(
        """INSERT INTO users (id, name, bracu_email, phone, password_hash, gender, role, is_verified)
           VALUES (?, ?, ?, ?, ?, ?, 'rider', 0)""",
        (user_id, body.name.strip(), email, phone, hashed, body.gender)
    )

    # Generate OTP
    otp_code = str(random.randint(100000, 999999))
    otp_id = str(uuid.uuid4())
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()

    conn.execute(
        "INSERT INTO otp_codes (id, email, code, expires_at) VALUES (?, ?, ?, ?)",
        (otp_id, email, otp_code, expires_at)
    )

    conn.commit()
    conn.close()

    # In production, this would send an email. For demo, we log it.
    print(f"\n[OTP] Code for {email}: {otp_code}\n")

    return {
        "message": "Registration successful! Please verify your email with the OTP sent.",
        "email": email,
        **(_otp_hint(otp_code)),  # DEMO_MODE only — never include in production
    }


@router.post("/verify-otp")
def verify_otp(body: VerifyOTPRequest, request: Request):
    """Verify OTP code sent during registration."""
    email = body.email.strip().lower()
    rate_key = _rate_key(request, email, "otp")
    _check_rate(rate_key)
    conn = get_db()

    # Find latest unused OTP for this email
    otp = conn.execute(
        """SELECT * FROM otp_codes WHERE email = ? AND is_used = 0
           ORDER BY created_at DESC LIMIT 1""",
        (email,)
    ).fetchone()

    if not otp:
        conn.close()
        raise HTTPException(status_code=400, detail="No pending OTP found for this email")

    # Check expiry
    if datetime.fromisoformat(otp["expires_at"]) < datetime.utcnow():
        conn.close()
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    # Check code
    if otp["code"] != body.code:
        _record_rate(rate_key)
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid OTP code")

    # Mark OTP as used and verify user
    conn.execute("UPDATE otp_codes SET is_used = 1 WHERE id = ?", (otp["id"],))
    conn.execute("UPDATE users SET is_verified = 1 WHERE bracu_email = ?", (email,))
    conn.commit()

    # Get user and create token
    user = conn.execute("SELECT * FROM users WHERE bracu_email = ?", (email,)).fetchone()
    conn.close()

    token = create_access_token({"sub": user["id"], "email": user["bracu_email"], "role": user["role"]})

    return {
        "message": "Email verified successfully!",
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["bracu_email"],
            "role": user["role"],
            "gender": user["gender"],
        }
    }


@router.post("/login")
def login(body: LoginRequest, request: Request):
    """Login with BRACU email and password."""
    email = body.email.strip().lower()
    rate_key = _rate_key(request, email, "login")
    _check_rate(rate_key)
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE bracu_email = ?", (email,)).fetchone()
    conn.close()

    if not user or not verify_password(body.password, user["password_hash"]):
        _record_rate(rate_key)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user["is_verified"]:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in")

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Your account has been deactivated")

    token = create_access_token({"sub": user["id"], "email": user["bracu_email"], "role": user["role"]})

    return {
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["bracu_email"],
            "role": user["role"],
            "gender": user["gender"],
            "phone": user["phone"],
        }
    }


@router.get("/me")
def get_current_user(user_id: str = Depends(get_current_user_id)):
    """Get current authenticated user's info."""
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["bracu_email"],
        "role": user["role"],
        "gender": user["gender"],
        "phone": user["phone"],
        "is_verified": bool(user["is_verified"]),
        "created_at": user["created_at"],
    }


@router.post("/resend-otp")
def resend_otp(body: ResendOTPRequest):
    """Resend OTP to a registered but unverified email.

    Improvement note:
    - Normalizes the email before lookup.
    - Reuses the pending verification flow, which is safer for the shared student-auth flow.
    - Now takes a Pydantic model instead of a raw dict (consistency + validation).
    """
    email = body.email.strip().lower()
    conn = get_db()
    user = conn.execute("SELECT id, is_verified FROM users WHERE bracu_email = ?", (email,)).fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="No account found with this email")

    if user["is_verified"]:
        conn.close()
        raise HTTPException(status_code=400, detail="This email is already verified")

    otp_code = str(random.randint(100000, 999999))
    otp_id = str(uuid.uuid4())
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()

    conn.execute(
        "INSERT INTO otp_codes (id, email, code, expires_at) VALUES (?, ?, ?, ?)",
        (otp_id, email, otp_code, expires_at)
    )
    conn.commit()
    conn.close()

    print(f"\n[OTP] Resent code for {email}: {otp_code}\n")

    return {
        "message": "New OTP sent to your email",
        **(_otp_hint(otp_code)),  # DEMO_MODE only — never include in production
    }

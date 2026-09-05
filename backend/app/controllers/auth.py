"""Auth controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends, Request
from app.controllers.dependencies import get_current_user_id
from app.models import auth as model
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    VerifyOTPRequest,
    ResendOTPRequest,
)

router = APIRouter()


@router.post("/register")
def register(body: RegisterRequest):
    """Register a new student — BRACU email only.

    Notes:
    - This module remains part of the shared Sprint-1 authentication foundation.
    - Ornab's Sprint-2 work depends on the verified BRACU identity gate.
    """
    return model.register(body=body)


@router.post("/verify-otp")
def verify_otp(body: VerifyOTPRequest, request: Request):
    """Verify OTP code sent during registration."""
    return model.verify_otp(
        body=body, client_ip=request.client.host if request.client else "unknown"
    )


@router.post("/login")
def login(body: LoginRequest, request: Request):
    """Login with BRACU email and password."""
    return model.login(
        body=body, client_ip=request.client.host if request.client else "unknown"
    )


@router.get("/me")
def get_current_user(user_id: str = Depends(get_current_user_id)):
    """Get current authenticated user's info."""
    return model.get_current_user(user_id=user_id)


@router.post("/resend-otp")
def resend_otp(body: ResendOTPRequest):
    """Resend OTP to a registered but unverified email.

    Improvement note:
    - Normalizes the email before lookup.
    - Reuses the pending verification flow, which is safer for the shared student-auth flow.
    - Now takes a Pydantic model instead of a raw dict (consistency + validation).
    """
    return model.resend_otp(body=body)

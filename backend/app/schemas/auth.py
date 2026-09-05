"""Validated request data for auth; no persistence or HTTP handlers."""

from pydantic import BaseModel


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

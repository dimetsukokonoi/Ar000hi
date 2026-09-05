"""Validated request data for tracking; no persistence or HTTP handlers."""

from pydantic import BaseModel


class TrackingPointRequest(BaseModel):
    session_id: str
    lat: float
    lng: float


class StartSessionRequest(BaseModel):
    pass  # No body needed, user_id from token

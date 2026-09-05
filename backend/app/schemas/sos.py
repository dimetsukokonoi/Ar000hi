"""Validated request data for sos; no persistence or HTTP handlers."""

from pydantic import BaseModel


class SOSRequest(BaseModel):
    lat: float
    lng: float
    session_id: str | None = None

"""Validated request data for contacts; no persistence or HTTP handlers."""

from pydantic import BaseModel


class ContactRequest(BaseModel):
    contact_name: str
    contact_phone: str
    contact_email: str = ""


class AutoShareRequest(BaseModel):
    share_url: str
    session_id: str | None = None

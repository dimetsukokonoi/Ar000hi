"""Validated request data for complaints; no persistence or HTTP handlers."""

from pydantic import BaseModel


class CreateComplaintRequest(BaseModel):
    category: str  # safety, misconduct, vehicle, payment, other
    subject: str
    description: str
    reported_id: str | None = None


class UpdateComplaintRequest(BaseModel):
    status: str  # open, under_review, resolved, dismissed
    admin_notes: str = ""

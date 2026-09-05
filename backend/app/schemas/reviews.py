"""Validated request data for reviews; no persistence or HTTP handlers."""

from pydantic import BaseModel


class ReviewRequest(BaseModel):
    ride_id: str
    reviewee_id: str
    stars: int
    comment: str = ""

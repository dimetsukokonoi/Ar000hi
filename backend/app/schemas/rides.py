"""Validated request data for rides; no persistence or HTTP handlers."""

from pydantic import BaseModel


class CreateRideRequest(BaseModel):
    source: str
    destination: str
    base_fare: float
    total_seats: int = 4
    scheduled_at: str | None = None
    female_only: bool = False
    stops: list[str] = []


class JoinRideRequest(BaseModel):
    seats: int = 1
    pickup_stop: str | None = None
    dropoff_stop: str | None = None

    def model_post_init(self, __context):
        if self.seats < 1:
            raise ValueError("seats must be at least 1")


class EndRideRequest(BaseModel):
    distance_km: float | None = None


class UpdateStopStatusRequest(BaseModel):
    status: str  # 'pending', 'reached', 'departed'


class CancelRideRequest(BaseModel):
    reason: str = ""

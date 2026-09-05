sx"""Rides controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends
from app.controllers.dependencies import get_current_user_id
from app.models import rides as model
from app.schemas.rides import (
    CreateRideRequest,
    JoinRideRequest,
    EndRideRequest,
    UpdateStopStatusRequest,
    CancelRideRequest,
)

router = APIRouter()


@router.get("/hotspots")
def get_hotspots():
    """Returns categorized campus pickup hotspots and transit points."""
    return model.get_hotspots()


@router.post("")
def create_ride(body: CreateRideRequest, user_id: str = Depends(get_current_user_id)):
    """Driver creates a new ride with multi-stop and scheduling support."""
    return model.create_ride(body=body, user_id=user_id)


@router.post("/{ride_id}/join")
def join_ride(
    ride_id: str, body: JoinRideRequest, user_id: str = Depends(get_current_user_id)
):
    """Rider requests a seat on a ride, optionally specifying their pickup and drop-off stops."""
    return model.join_ride(ride_id=ride_id, body=body, user_id=user_id)


@router.post("/{ride_id}/accept/{passenger_id}")
def accept_passenger(
    ride_id: str, passenger_id: str, user_id: str = Depends(get_current_user_id)
):
    """Driver accepts a passenger's ride request."""
    return model.accept_passenger(
        ride_id=ride_id, passenger_id=passenger_id, user_id=user_id
    )


@router.post("/{ride_id}/stops/{stop_id}/status")
def update_stop_status(
    ride_id: str,
    stop_id: str,
    body: UpdateStopStatusRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Driver updates progress of a stop (pending, reached, departed)."""
    return model.update_stop_status(
        ride_id=ride_id, stop_id=stop_id, body=body, user_id=user_id
    )


@router.post("/{ride_id}/start")
def start_ride(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """Driver starts the ride."""
    return model.start_ride(ride_id=ride_id, user_id=user_id)


@router.post("/{ride_id}/end")
def end_ride(
    ride_id: str, body: EndRideRequest, user_id: str = Depends(get_current_user_id)
):
    """Driver ends the ride — computes distance (tracking points or estimate) for eco tracking."""
    return model.end_ride(ride_id=ride_id, body=body, user_id=user_id)


@router.get("/match")
def match_rides(
    source: str | None = None,
    pickup: str | None = None,
    destination: str | None = None,
    dropoff: str | None = None,
    scheduled_date: str | None = None,
    scheduled_time: str | None = None,
    class_time: str | None = None,
    female_only: bool = False,
    user_id: str = Depends(get_current_user_id),
):
    """Smart Matching Algorithm:
    Matches riders with open rides heading to their destination or passing through their intermediate stops.
    Supports proximity zone matching, class schedule time-flex matching, and female-only filtering.
    """
    return model.match_rides(
        source=source,
        pickup=pickup,
        destination=destination,
        dropoff=dropoff,
        scheduled_date=scheduled_date,
        scheduled_time=scheduled_time,
        class_time=class_time,
        female_only=female_only,
        user_id=user_id,
    )


@router.get("")
def list_rides(female_only: bool = False, user_id: str = Depends(get_current_user_id)):
    """List rides: mine (as driver/passenger) + open available rides."""
    return model.list_rides(female_only=female_only, user_id=user_id)


@router.get("/{ride_id}")
def get_ride(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """Ride detail including passenger stops and multi-stop progress."""
    return model.get_ride(ride_id=ride_id, user_id=user_id)


@router.get("/{ride_id}/split")
def ride_cost_split(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """Ride Cost Splitter — total = base_fare x surge; split by SEATS among accepted
    passengers, with whole-taka largest-remainder rounding so shares sum exactly
    to `total`.
    """
    return model.ride_cost_split(ride_id=ride_id, user_id=user_id)


@router.get("/{ride_id}/messages")
def get_ride_messages(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """Ride Chat history (participants only)."""
    return model.get_ride_messages(ride_id=ride_id, user_id=user_id)


@router.get("/{ride_id}/cancellation-policy")
def cancellation_policy(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """Preview what cancelling costs, so the UI can warn before anything happens."""
    return model.cancellation_policy(ride_id=ride_id, user_id=user_id)


@router.post("/{ride_id}/cancel")
def cancel_ride(
    ride_id: str, body: CancelRideRequest, user_id: str = Depends(get_current_user_id)
):
    """Driver cancels the whole ride; a passenger cancels only their own seat."""
    return model.cancel_ride(ride_id=ride_id, body=body, user_id=user_id)

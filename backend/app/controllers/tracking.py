"""Tracking controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends
from app.controllers.dependencies import get_current_user_id
from app.models import tracking as model
from app.schemas.tracking import TrackingPointRequest

router = APIRouter()


@router.post("/session")
def start_tracking_session(user_id: str = Depends(get_current_user_id)):
    """Start a new GPS tracking session."""
    return model.start_tracking_session(user_id=user_id)


@router.post("/point")
def add_tracking_point(
    body: TrackingPointRequest, user_id: str = Depends(get_current_user_id)
):
    """Add a GPS coordinate point to an active tracking session."""
    return model.add_tracking_point(body=body, user_id=user_id)


@router.get("/session/{session_id}")
def get_session_points(session_id: str, user_id: str = Depends(get_current_user_id)):
    """Get all tracking points for a session (owner only — fix: was leaking any session)."""
    return model.get_session_points(session_id=session_id, user_id=user_id)


@router.get("/share/{share_token}")
def get_shared_tracking(share_token: str):
    """Public: Get tracking data via share token (for trusted contacts)."""
    return model.get_shared_tracking(share_token=share_token)


@router.post("/session/{session_id}/stop")
def stop_tracking_session(session_id: str, user_id: str = Depends(get_current_user_id)):
    """Stop an active tracking session.

    Improvement note:
    - Keeps the shared live GPS tracking flow aligned with the expedition of ride monitoring and trusted-contact sharing.
    """
    return model.stop_tracking_session(session_id=session_id, user_id=user_id)


@router.get("/active")
def get_active_session(user_id: str = Depends(get_current_user_id)):
    """Get the user's currently active tracking session, if any."""
    return model.get_active_session(user_id=user_id)

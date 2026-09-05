"""Sos controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends
from app.controllers.dependencies import get_current_user_id, require_admin
from app.models import sos as model
from app.schemas.sos import SOSRequest

router = APIRouter()


@router.post("/trigger")
def trigger_sos(body: SOSRequest, user_id: str = Depends(get_current_user_id)):
    """Trigger an SOS alert — notifies trusted contacts and campus security."""
    return model.trigger_sos(body=body, user_id=user_id)


@router.get("/alerts")
def get_sos_alerts(admin_id: str = Depends(require_admin)):
    """Admin: Get all SOS alerts."""
    return model.get_sos_alerts(admin_id=admin_id)


@router.patch("/{alert_id}/resolve")
def resolve_sos(alert_id: str, body: dict, admin_id: str = Depends(require_admin)):
    """Admin: Resolve an SOS alert."""
    return model.resolve_sos(alert_id=alert_id, body=body, admin_id=admin_id)


@router.get("/my-alerts")
def get_my_sos_alerts(user_id: str = Depends(get_current_user_id)):
    """Get current user's SOS alert history."""
    return model.get_my_sos_alerts(user_id=user_id)

"""Surge controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends
from app.controllers.dependencies import get_current_user_id
from app.models import surge as model

router = APIRouter()


@router.get("/current")
def get_current_surge(user_id: str = Depends(get_current_user_id)):
    """Current surge multiplier + label based on the hour and live ride volume.

    Improvement note:
    - The surge state remains a lightweight live demand indicator for the ride planner view.
    """
    return model.get_current_surge(user_id=user_id)


@router.get("/schedule")
def get_surge_schedule(user_id: str = Depends(get_current_user_id)):
    """Hourly surge schedule (0-23) — used to warn users of upcoming peak windows.

    Fix (PROJECT_PLAN.md §6.2): the live active-ride bump now applies ONLY to the
    current hour. Other hours show their seeded baseline so the schedule reads as a
    proper forecast instead of shifting all 24 hours by the same amount.
    """
    return model.get_surge_schedule(user_id=user_id)

"""Eco controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends
from app.controllers.dependencies import get_current_user_id
from app.models import eco as model

router = APIRouter()


@router.get("/stats")
def get_eco_stats(user_id: str = Depends(get_current_user_id)):
    """Aggregate eco stats for the current user across their completed rides."""
    return model.get_eco_stats(user_id=user_id)


@router.get("/leaderboard")
def get_eco_leaderboard(user_id: str = Depends(get_current_user_id)):
    """Gamified public ranking of top CO2 savers (Feature 20 improvement).

    Aggregates saved_kg per user across completed rides they drove OR joined,
    then returns the top 10. The requesting user's own rank is also included
    if they fall outside the top 10.
    """
    return model.get_eco_leaderboard(user_id=user_id)

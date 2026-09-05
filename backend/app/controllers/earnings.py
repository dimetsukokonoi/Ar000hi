"""Earnings controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends, Query
from app.controllers.dependencies import get_current_user_id
from app.models import earnings as model

router = APIRouter()


@router.get("/summary")
def earnings_summary(user_id: str = Depends(get_current_user_id)):
    """Headline figures: lifetime net, ride count, this week vs last, payout ready."""
    return model.earnings_summary(user_id=user_id)


@router.get("/weekly")
def earnings_weekly(
    weeks: int = Query(8, ge=1, le=26), user_id: str = Depends(get_current_user_id)
):
    """Earnings per week (Monday start, Dhaka time), oldest first."""
    return model.earnings_weekly(weeks=weeks, user_id=user_id)


@router.get("/daily")
def earnings_daily(
    days: int = Query(14, ge=1, le=90), user_id: str = Depends(get_current_user_id)
):
    """Earnings per calendar day (Dhaka time), oldest first.

    Expect this view to look sparse: a student driver runs a handful of rides a
    week, so most days are legitimately zero.
    """
    return model.earnings_daily(days=days, user_id=user_id)


@router.get("/rides")
def earnings_rides(
    limit: int = Query(20, ge=1, le=100), user_id: str = Depends(get_current_user_id)
):
    """Per-ride earnings, newest first, with unsettled rides flagged."""
    return model.earnings_rides(limit=limit, user_id=user_id)

"""Reviews controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends
from app.controllers.dependencies import get_current_user_id
from app.models import reviews as model
from app.schemas.reviews import ReviewRequest

router = APIRouter()


@router.post("")
def create_review(body: ReviewRequest, user_id: str = Depends(get_current_user_id)):
    """Leave a 1-5 star review with an optional comment, after a completed ride."""
    return model.create_review(body=body, user_id=user_id)


@router.get("/pending")
def pending_reviews(user_id: str = Depends(get_current_user_id)):
    """Completed rides where this user still owes the driver a review.

    Drives the post-ride prompt: the app should ask once, then stop asking.
    """
    return model.pending_reviews(user_id=user_id)


@router.get("/me")
def my_reviews(user_id: str = Depends(get_current_user_id)):
    """Reviews this user has received, plus their average."""
    return model.my_reviews(user_id=user_id)


@router.get("/driver/{driver_id}")
def driver_reviews(driver_id: str, user_id: str = Depends(get_current_user_id)):
    """Public profile rating: average, star histogram and recent comments."""
    return model.driver_reviews(driver_id=driver_id, user_id=user_id)

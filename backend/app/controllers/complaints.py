"""Complaints controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends
from app.controllers.dependencies import get_current_user_id, require_admin
from app.models import complaints as model
from app.schemas.complaints import CreateComplaintRequest, UpdateComplaintRequest

router = APIRouter()


@router.post("/")
def create_complaint(
    body: CreateComplaintRequest, user_id: str = Depends(get_current_user_id)
):
    """File a new complaint.

    Improvement note:
    - This shared admin moderation API is now stricter about complaint content before it reaches the moderator queue.
    """
    return model.create_complaint(body=body, user_id=user_id)


@router.get("/")
def get_complaints(user_id: str = Depends(get_current_user_id)):
    """Get complaints — own complaints for users, all complaints for admin."""
    return model.get_complaints(user_id=user_id)


@router.patch("/{complaint_id}")
def update_complaint(
    complaint_id: str,
    body: UpdateComplaintRequest,
    admin_id: str = Depends(require_admin),
):
    """Admin: Update complaint status and add notes."""
    return model.update_complaint(
        complaint_id=complaint_id, body=body, admin_id=admin_id
    )


@router.get("/stats")
def get_complaint_stats(admin_id: str = Depends(require_admin)):
    """Admin: Get complaint statistics."""
    return model.get_complaint_stats(admin_id=admin_id)

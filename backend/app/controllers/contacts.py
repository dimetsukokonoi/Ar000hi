"""Contacts controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends
from app.controllers.dependencies import get_current_user_id
from app.models import contacts as model
from app.schemas.contacts import ContactRequest, AutoShareRequest

router = APIRouter()


@router.get("")
def list_contacts(user_id: str = Depends(get_current_user_id)):
    """List the current user's trusted contacts."""
    return model.list_contacts(user_id=user_id)


@router.post("")
def add_contact(body: ContactRequest, user_id: str = Depends(get_current_user_id)):
    """Add a trusted contact for the current user."""
    return model.add_contact(body=body, user_id=user_id)


@router.delete("/{contact_id}")
def remove_contact(contact_id: str, user_id: str = Depends(get_current_user_id)):
    """Remove a trusted contact (owner only)."""
    return model.remove_contact(contact_id=contact_id, user_id=user_id)


@router.post("/auto-share")
def auto_share(body: AutoShareRequest, user_id: str = Depends(get_current_user_id)):
    """Auto-share ride/live-tracking details to all trusted contacts.

    Improvement note:
    - The module remains a demo-safe integration point for trusted-contact sharing.
    - The share is now PERSISTED to `contact_shares` (auditable history, see
      GET /api/contacts/shares) in addition to the console log.
    - Production should replace the console delivery with provider-backed SMS/email/push.
    """
    return model.auto_share(body=body, user_id=user_id)


@router.get("/shares")
def list_shares(user_id: str = Depends(get_current_user_id)):
    """Share history for the current user (Feature 12: auditable auto-share log)."""
    return model.list_shares(user_id=user_id)

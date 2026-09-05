"""Drivers controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends, UploadFile, File, Form
from app.controllers.dependencies import get_current_user_id, require_admin
from app.models import drivers as model

router = APIRouter()


@router.post("/verify")
async def submit_driver_verification(
    vehicle_type: str = Form(...),
    vehicle_model: str = Form(...),
    vehicle_plate: str = Form(...),
    nid_document: UploadFile = File(...),
    license_document: UploadFile = File(...),
    vehicle_registration: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Submit driver documents for verification."""
    from app.models.uploads import UploadedDocument

    nid_document_data = UploadedDocument(
        nid_document.filename, nid_document.content_type, await nid_document.read()
    )
    license_document_data = UploadedDocument(
        license_document.filename,
        license_document.content_type,
        await license_document.read(),
    )
    vehicle_registration_data = UploadedDocument(
        vehicle_registration.filename,
        vehicle_registration.content_type,
        await vehicle_registration.read(),
    )
    return await model.submit_driver_verification(
        vehicle_type=vehicle_type,
        vehicle_model=vehicle_model,
        vehicle_plate=vehicle_plate,
        nid_document=nid_document_data,
        license_document=license_document_data,
        vehicle_registration=vehicle_registration_data,
        user_id=user_id,
    )


@router.get("/status")
def get_driver_status(user_id: str = Depends(get_current_user_id)):
    """Get the current driver verification status."""
    return model.get_driver_status(user_id=user_id)


@router.get("/pending")
def get_pending_drivers(
    status: str = "pending",
    admin_id: str = Depends(require_admin),
):
    """Admin: driver verification requests, filterable by status.

    Fix (PROJECT_PLAN.md §6.2): the endpoint was misnamed — it returned ALL statuses.
    Now it defaults to `pending` (matching the name) and supports
    `?status=all|pending|approved|rejected` for the admin review UI.
    """
    return model.get_pending_drivers(status=status, admin_id=admin_id)


@router.patch("/{profile_id}/review")
def review_driver(profile_id: str, body: dict, admin_id: str = Depends(require_admin)):
    """Admin: Approve or reject a driver application."""
    return model.review_driver(profile_id=profile_id, body=body, admin_id=admin_id)

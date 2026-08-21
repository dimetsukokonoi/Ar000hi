"""
Arooohi Backend — Driver Verification Routes
Feature 2: Driver Vehicle Verification
"""
import uuid
import os
import shutil
from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from app.database import get_db
from app.auth import get_current_user_id, require_admin
from app.routes.reviews import rating_for

router = APIRouter()

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "uploads")
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024
# Extension is derived from the validated MIME type, NOT from the client filename
# (fixes arbitrary-extension preservation — a stored-XSS/upload-abuse risk).
MIME_TO_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}


async def save_upload(file: UploadFile, subfolder: str) -> str:
    """Save an uploaded document safely and return its URL path.

    Improvement note:
    - This keeps the Sprint-1 driver verification module safer for admin review.
    - Files are still stored locally for the demo setup, but the validation is now stricter.
    - The stored extension comes from the MIME type, not the client-supplied filename.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Please attach a document file")

    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type. Upload JPG, PNG, or PDF.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File is too large. Upload a file smaller than 2MB.")

    os.makedirs(os.path.join(UPLOADS_DIR, subfolder), exist_ok=True)
    ext = MIME_TO_EXT[mime]
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOADS_DIR, subfolder, filename)

    with open(filepath, "wb") as f:
        f.write(content)

    return f"/uploads/{subfolder}/{filename}"


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
    conn = get_db()

    # Check if profile already exists
    existing = conn.execute(
        "SELECT id, verification_status FROM driver_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()

    if existing and existing["verification_status"] == "approved":
        conn.close()
        raise HTTPException(status_code=400, detail="Your driver profile is already approved")

    # Save uploaded files
    nid_url = await save_upload(nid_document, "nid")
    license_url = await save_upload(license_document, "license")
    vehicle_url = await save_upload(vehicle_registration, "vehicle")

    if existing:
        # Update existing profile
        conn.execute(
            """UPDATE driver_profiles SET
               nid_document_url = ?, license_document_url = ?, vehicle_registration_url = ?,
               vehicle_type = ?, vehicle_model = ?, vehicle_plate = ?,
               verification_status = 'pending', admin_notes = ''
               WHERE user_id = ?""",
            (nid_url, license_url, vehicle_url, vehicle_type, vehicle_model, vehicle_plate, user_id)
        )
    else:
        # Create new profile
        profile_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO driver_profiles
               (id, user_id, nid_document_url, license_document_url, vehicle_registration_url,
                vehicle_type, vehicle_model, vehicle_plate)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (profile_id, user_id, nid_url, license_url, vehicle_url,
             vehicle_type, vehicle_model, vehicle_plate)
        )

    # Keep the user in a pending driver-review state until the admin approves the submission.
    conn.commit()
    conn.close()

    return {"message": "Documents submitted successfully! Awaiting admin verification."}


@router.get("/status")
def get_driver_status(user_id: str = Depends(get_current_user_id)):
    """Get the current driver verification status."""
    conn = get_db()
    profile = conn.execute(
        "SELECT * FROM driver_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()

    # Feature 7: the driver's public star rating belongs on their profile. Read it
    # BEFORE the not-submitted early return — ratings come from completed rides, which
    # a user can have without ever having filed vehicle documents.
    rating = rating_for(conn, user_id)

    if not profile:
        conn.close()
        return {"status": "not_submitted", "profile": None, "rating": rating}

    conn.close()

    return {
        "status": profile["verification_status"],
        "rating": rating,
        "profile": {
            "id": profile["id"],
            "vehicle_type": profile["vehicle_type"],
            "vehicle_model": profile["vehicle_model"],
            "vehicle_plate": profile["vehicle_plate"],
            "nid_document_url": profile["nid_document_url"],
            "license_document_url": profile["license_document_url"],
            "vehicle_registration_url": profile["vehicle_registration_url"],
            "admin_notes": profile["admin_notes"],
            "created_at": profile["created_at"],
        }
    }


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
    if status not in ("all", "pending", "approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be all, pending, approved, or rejected")

    conn = get_db()
    if status == "all":
        profiles = conn.execute(
            """SELECT dp.*, u.name, u.bracu_email, u.phone, u.gender
               FROM driver_profiles dp
               JOIN users u ON dp.user_id = u.id
               ORDER BY dp.created_at DESC"""
        ).fetchall()
    else:
        profiles = conn.execute(
            """SELECT dp.*, u.name, u.bracu_email, u.phone, u.gender
               FROM driver_profiles dp
               JOIN users u ON dp.user_id = u.id
               WHERE dp.verification_status = ?
               ORDER BY dp.created_at DESC""",
            (status,)
        ).fetchall()
    conn.close()

    return [
        {
            "id": p["id"],
            "user_id": p["user_id"],
            "name": p["name"],
            "email": p["bracu_email"],
            "phone": p["phone"],
            "gender": p["gender"],
            "vehicle_type": p["vehicle_type"],
            "vehicle_model": p["vehicle_model"],
            "vehicle_plate": p["vehicle_plate"],
            "nid_document_url": p["nid_document_url"],
            "license_document_url": p["license_document_url"],
            "vehicle_registration_url": p["vehicle_registration_url"],
            "verification_status": p["verification_status"],
            "admin_notes": p["admin_notes"],
            "created_at": p["created_at"],
        }
        for p in profiles
    ]


@router.patch("/{profile_id}/review")
def review_driver(profile_id: str, body: dict, admin_id: str = Depends(require_admin)):
    """Admin: Approve or reject a driver application."""
    status = body.get("status")
    notes = body.get("admin_notes", "")

    if status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Status must be 'approved' or 'rejected'")

    conn = get_db()
    profile = conn.execute("SELECT user_id FROM driver_profiles WHERE id = ?", (profile_id,)).fetchone()

    if not profile:
        conn.close()
        raise HTTPException(status_code=404, detail="Driver profile not found")

    conn.execute(
        "UPDATE driver_profiles SET verification_status = ?, admin_notes = ? WHERE id = ?",
        (status, notes, profile_id)
    )

    if status == "approved":
        conn.execute("UPDATE users SET role = 'driver' WHERE id = ?", (profile["user_id"],))
    else:
        conn.execute("UPDATE users SET role = 'rider' WHERE id = ?", (profile["user_id"],))

    conn.commit()
    conn.close()

    return {"message": f"Driver application {status}", "status": status}

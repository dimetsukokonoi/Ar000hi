"""
Arooohi Backend — Trusted Contacts Routes
Feature 12: Trusted Contact Sharing  (Ornab)
Backend CRUD for the trusted_contacts table so SOS + auto-share use real saved contacts.
"""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.auth import get_current_user_id

router = APIRouter()


class ContactRequest(BaseModel):
    contact_name: str
    contact_phone: str
    contact_email: str = ""


@router.get("")
def list_contacts(user_id: str = Depends(get_current_user_id)):
    """List the current user's trusted contacts."""
    conn = get_db()
    contacts = conn.execute(
        "SELECT * FROM trusted_contacts WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [
        {
            "id": c["id"],
            "contact_name": c["contact_name"],
            "contact_phone": c["contact_phone"],
            "contact_email": c["contact_email"],
            "created_at": c["created_at"],
        }
        for c in contacts
    ]


@router.post("")
def add_contact(body: ContactRequest, user_id: str = Depends(get_current_user_id)):
    """Add a trusted contact for the current user."""
    if not body.contact_name.strip() or not body.contact_phone.strip():
        raise HTTPException(status_code=400, detail="Name and phone are required")

    contact_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        """INSERT INTO trusted_contacts (id, user_id, contact_name, contact_phone, contact_email)
           VALUES (?, ?, ?, ?, ?)""",
        (contact_id, user_id, body.contact_name.strip(), body.contact_phone.strip(), body.contact_email.strip())
    )
    conn.commit()
    conn.close()

    return {
        "message": "Trusted contact added",
        "contact": {
            "id": contact_id,
            "contact_name": body.contact_name.strip(),
            "contact_phone": body.contact_phone.strip(),
            "contact_email": body.contact_email.strip(),
        }
    }


@router.delete("/{contact_id}")
def remove_contact(contact_id: str, user_id: str = Depends(get_current_user_id)):
    """Remove a trusted contact (owner only)."""
    conn = get_db()
    result = conn.execute(
        "DELETE FROM trusted_contacts WHERE id = ? AND user_id = ?",
        (contact_id, user_id)
    )
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"message": "Trusted contact removed"}


class AutoShareRequest(BaseModel):
    share_url: str
    session_id: str | None = None


@router.post("/auto-share")
def auto_share(body: AutoShareRequest, user_id: str = Depends(get_current_user_id)):
    """Auto-share ride/live-tracking details to all trusted contacts.
    Mocked delivery (console log) — same pattern as the SOS alert flow."""
    conn = get_db()
    user = conn.execute("SELECT name, bracu_email FROM users WHERE id = ?", (user_id,)).fetchone()
    contacts = conn.execute(
        "SELECT contact_name, contact_phone FROM trusted_contacts WHERE user_id = ?",
        (user_id,)
    ).fetchall()
    conn.close()

    contacts_list = [
        {"name": c["contact_name"], "phone": c["contact_phone"]} for c in contacts
    ]

    # In production: send SMS/email/push with the share link to every contact.
    print(f"\n[SHARE] {user['name']} ({user['bracu_email']}) shared ride details")
    print(f"   Share URL: {body.share_url}")
    print(f"   Notified {len(contacts_list)} trusted contact(s):")
    for c in contacts_list:
        print(f"      -> {c['name']}: {c['phone']}")
    print()

    return {
        "message": f"Ride details shared with {len(contacts_list)} trusted contact(s)",
        "share_url": body.share_url,
        "contacts_notified": contacts_list,
    }

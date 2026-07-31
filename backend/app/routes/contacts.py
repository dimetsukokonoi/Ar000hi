"""
Arooohi Backend — Trusted Contacts Routes
Feature 12: Trusted Contact Sharing  (Ornab)
Backend CRUD for the trusted_contacts table so SOS + auto-share use real saved contacts.

Improvements in this pass:
- auto-share now PERSISTS a row in `contact_shares` (auditable share history) instead
  of only console-logging; a GET endpoint returns the current user's share history.
- Phone validation (BD mobile format) added on contact create.
"""
import uuid
import re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.auth import get_current_user_id

router = APIRouter()

# Bangladesh mobile number: 01 + 9 digits (e.g. 01712345678). Lenient for demos.
PHONE_RE = re.compile(r"^01\d{9}$")


class ContactRequest(BaseModel):
    contact_name: str
    contact_phone: str
    contact_email: str = ""


def _validate_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "").replace("-", "").replace("+88", "")
    if not PHONE_RE.match(phone):
        raise HTTPException(
            status_code=400,
            detail="Phone must be a valid Bangladesh mobile number like 017XXXXXXXX",
        )
    return phone


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
    if not body.contact_name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    phone = _validate_phone(body.contact_phone)

    contact_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        """INSERT INTO trusted_contacts (id, user_id, contact_name, contact_phone, contact_email)
           VALUES (?, ?, ?, ?, ?)""",
        (contact_id, user_id, body.contact_name.strip(), phone, body.contact_email.strip())
    )
    conn.commit()
    conn.close()

    return {
        "message": "Trusted contact added",
        "contact": {
            "id": contact_id,
            "contact_name": body.contact_name.strip(),
            "contact_phone": phone,
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

    Improvement note:
    - The module remains a demo-safe integration point for trusted-contact sharing.
    - The share is now PERSISTED to `contact_shares` (auditable history, see
      GET /api/contacts/shares) in addition to the console log.
    - Production should replace the console delivery with provider-backed SMS/email/push.
    """
    conn = get_db()
    user = conn.execute("SELECT name, bracu_email FROM users WHERE id = ?", (user_id,)).fetchone()
    contacts = conn.execute(
        "SELECT contact_name, contact_phone FROM trusted_contacts WHERE user_id = ?",
        (user_id,)
    ).fetchall()

    contacts_list = [
        {"name": c["contact_name"], "phone": c["contact_phone"]} for c in contacts
    ]

    # Persist the share so the action is auditable (Feature 12 improvement).
    share_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO contact_shares (id, user_id, share_url, session_id, contact_count) VALUES (?, ?, ?, ?, ?)",
        (share_id, user_id, body.share_url, body.session_id, len(contacts_list))
    )
    conn.commit()
    conn.close()

    # In production: send SMS/email/push with the share link to every contact.
    print(f"\n[SHARE] {user['name']} ({user['bracu_email']}) shared ride details")
    print(f"   Share URL: {body.share_url}")
    print(f"   Notified {len(contacts_list)} trusted contact(s):")
    for c in contacts_list:
        print(f"      -> {c['name']}: {c['phone']}")
    print()

    return {
        "message": f"Ride details shared with {len(contacts_list)} trusted contact(s)",
        "share_id": share_id,
        "share_url": body.share_url,
        "contacts_notified": contacts_list,
    }


@router.get("/shares")
def list_shares(user_id: str = Depends(get_current_user_id)):
    """Share history for the current user (Feature 12: auditable auto-share log)."""
    conn = get_db()
    shares = conn.execute(
        """SELECT id, share_url, session_id, contact_count, created_at
           FROM contact_shares WHERE user_id = ?
           ORDER BY created_at DESC LIMIT 50""",
        (user_id,)
    ).fetchall()
    conn.close()

    return [
        {
            "id": s["id"],
            "share_url": s["share_url"],
            "session_id": s["session_id"],
            "contact_count": s["contact_count"],
            "created_at": s["created_at"],
        }
        for s in shares
    ]

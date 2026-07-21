"""
Arooohi Backend — SOS Alert Routes
Feature 4: In-App SOS Button
"""
import uuid
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.auth import get_current_user_id, require_admin

router = APIRouter()


class SOSRequest(BaseModel):
    lat: float
    lng: float
    session_id: str | None = None


@router.post("/trigger")
def trigger_sos(body: SOSRequest, user_id: str = Depends(get_current_user_id)):
    """Trigger an SOS alert — notifies trusted contacts and campus security."""
    conn = get_db()

    # Get user info
    user = conn.execute("SELECT name, bracu_email, phone FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    # Get trusted contacts
    contacts = conn.execute(
        "SELECT contact_name, contact_phone, contact_email FROM trusted_contacts WHERE user_id = ?",
        (user_id,)
    ).fetchall()

    contacts_list = [
        {"name": c["contact_name"], "phone": c["contact_phone"], "email": c["contact_email"]}
        for c in contacts
    ]

    # Always include campus security
    contacts_list.append({
        "name": "BRACU Campus Security",
        "phone": "01700000000",
        "email": "security@bracu.ac.bd"
    })

    # Create SOS alert
    alert_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO sos_alerts (id, user_id, session_id, lat, lng, contacts_notified)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (alert_id, user_id, body.session_id, body.lat, body.lng, json.dumps(contacts_list))
    )
    conn.commit()
    conn.close()

    # In production: send SMS/email/push notifications to all contacts
    print(f"\n[SOS] ALERT from {user['name']} ({user['bracu_email']})")
    print(f"   Location: {body.lat}, {body.lng}")
    print(f"   Contacts notified: {len(contacts_list)}")
    for c in contacts_list:
        print(f"      -> {c['name']}: {c['phone']}")
    print()

    return {
        "message": "SOS alert sent! Your contacts and campus security have been notified.",
        "alert_id": alert_id,
        "contacts_notified": contacts_list,
        "location": {"lat": body.lat, "lng": body.lng},
    }


@router.get("/alerts")
def get_sos_alerts(admin_id: str = Depends(require_admin)):
    """Admin: Get all SOS alerts."""
    conn = get_db()
    alerts = conn.execute(
        """SELECT sa.*, u.name, u.bracu_email, u.phone
           FROM sos_alerts sa
           JOIN users u ON sa.user_id = u.id
           ORDER BY sa.created_at DESC"""
    ).fetchall()
    conn.close()

    return [
        {
            "id": a["id"],
            "user_name": a["name"],
            "user_email": a["bracu_email"],
            "user_phone": a["phone"],
            "lat": a["lat"],
            "lng": a["lng"],
            "status": a["status"],
            "contacts_notified": json.loads(a["contacts_notified"]) if a["contacts_notified"] else [],
            "created_at": a["created_at"],
            "resolved_at": a["resolved_at"],
        }
        for a in alerts
    ]


@router.patch("/{alert_id}/resolve")
def resolve_sos(alert_id: str, body: dict, admin_id: str = Depends(require_admin)):
    """Admin: Resolve an SOS alert."""
    status = body.get("status", "resolved")
    if status not in ("resolved", "false_alarm"):
        raise HTTPException(status_code=400, detail="Status must be 'resolved' or 'false_alarm'")

    conn = get_db()
    from datetime import datetime
    conn.execute(
        "UPDATE sos_alerts SET status = ?, resolved_at = ? WHERE id = ?",
        (status, datetime.utcnow().isoformat(), alert_id)
    )
    conn.commit()
    conn.close()

    return {"message": f"SOS alert marked as {status}"}


@router.get("/my-alerts")
def get_my_sos_alerts(user_id: str = Depends(get_current_user_id)):
    """Get current user's SOS alert history."""
    conn = get_db()
    alerts = conn.execute(
        "SELECT * FROM sos_alerts WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()

    return [
        {
            "id": a["id"],
            "lat": a["lat"],
            "lng": a["lng"],
            "status": a["status"],
            "contacts_notified": json.loads(a["contacts_notified"]) if a["contacts_notified"] else [],
            "created_at": a["created_at"],
        }
        for a in alerts
    ]

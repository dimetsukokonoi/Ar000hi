"""
Arooohi Backend — GPS Tracking Routes
Feature 2: Live GPS Ride Tracking  (Sami's Sprint-1 module; improved by Ornab's agent pass)
Improvements in this pass:
- Share token is now a full 32-hex UUID (was 12 hex chars ≈ 48 bits — too guessable).
- get_session_points now enforces ownership (any authed user could previously read
  any session's points).
- stop_tracking_session reports 404 when the session doesn't exist/doesn't belong.
"""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.auth import get_current_user_id

router = APIRouter()


class TrackingPointRequest(BaseModel):
    session_id: str
    lat: float
    lng: float


class StartSessionRequest(BaseModel):
    pass  # No body needed, user_id from token


@router.post("/session")
def start_tracking_session(user_id: str = Depends(get_current_user_id)):
    """Start a new GPS tracking session."""
    conn = get_db()

    # Deactivate any existing active sessions for this user
    conn.execute(
        "UPDATE tracking_sessions SET is_active = 0 WHERE user_id = ? AND is_active = 1",
        (user_id,)
    )

    session_id = str(uuid.uuid4())
    share_token = uuid.uuid4().hex  # 32-hex (128 bits) — no longer a weak 12-char token

    conn.execute(
        "INSERT INTO tracking_sessions (id, user_id, share_token) VALUES (?, ?, ?)",
        (session_id, user_id, share_token)
    )
    conn.commit()
    conn.close()

    return {
        "session_id": session_id,
        "share_token": share_token,
        "share_url": f"http://localhost:3000/track/{share_token}",
        "message": "Tracking session started"
    }


@router.post("/point")
def add_tracking_point(body: TrackingPointRequest, user_id: str = Depends(get_current_user_id)):
    """Add a GPS coordinate point to an active tracking session."""
    conn = get_db()

    # Verify session belongs to user and is active
    session = conn.execute(
        "SELECT * FROM tracking_sessions WHERE id = ? AND user_id = ? AND is_active = 1",
        (body.session_id, user_id)
    ).fetchone()

    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Active tracking session not found")

    point_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO tracking_points (id, session_id, user_id, lat, lng) VALUES (?, ?, ?, ?, ?)",
        (point_id, body.session_id, user_id, body.lat, body.lng)
    )
    conn.commit()
    conn.close()

    return {"message": "Point recorded", "point_id": point_id}


@router.get("/session/{session_id}")
def get_session_points(session_id: str, user_id: str = Depends(get_current_user_id)):
    """Get all tracking points for a session (owner only — fix: was leaking any session)."""
    conn = get_db()
    session = conn.execute(
        "SELECT id FROM tracking_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id)
    ).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Tracking session not found")

    points = conn.execute(
        "SELECT * FROM tracking_points WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,)
    ).fetchall()
    conn.close()

    return [
        {"id": p["id"], "lat": p["lat"], "lng": p["lng"], "created_at": p["created_at"]}
        for p in points
    ]


@router.get("/share/{share_token}")
def get_shared_tracking(share_token: str):
    """Public: Get tracking data via share token (for trusted contacts)."""
    conn = get_db()

    session = conn.execute(
        "SELECT * FROM tracking_sessions WHERE share_token = ?",
        (share_token,)
    ).fetchone()

    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Tracking session not found")

    # Get user name (not email — privacy)
    user = conn.execute("SELECT name FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    # Get latest points
    points = conn.execute(
        """SELECT lat, lng, created_at FROM tracking_points
           WHERE session_id = ? ORDER BY created_at ASC""",
        (session["id"],)
    ).fetchall()
    conn.close()

    return {
        "user_name": user["name"] if user else "Unknown",
        "is_active": bool(session["is_active"]),
        "started_at": session["created_at"],
        "points": [
            {"lat": p["lat"], "lng": p["lng"], "created_at": p["created_at"]}
            for p in points
        ],
        "latest": {"lat": points[-1]["lat"], "lng": points[-1]["lng"]} if points else None,
    }


@router.post("/session/{session_id}/stop")
def stop_tracking_session(session_id: str, user_id: str = Depends(get_current_user_id)):
    """Stop an active tracking session.

    Improvement note:
    - Keeps the shared live GPS tracking flow aligned with the expedition of ride monitoring and trusted-contact sharing.
    """
    conn = get_db()
    result = conn.execute(
        "UPDATE tracking_sessions SET is_active = 0 WHERE id = ? AND user_id = ? AND is_active = 1",
        (session_id, user_id)
    )
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Tracking session not found")
    return {"message": "Tracking session stopped"}


@router.get("/active")
def get_active_session(user_id: str = Depends(get_current_user_id)):
    """Get the user's currently active tracking session, if any."""
    conn = get_db()
    session = conn.execute(
        "SELECT * FROM tracking_sessions WHERE user_id = ? AND is_active = 1",
        (user_id,)
    ).fetchone()
    conn.close()

    if not session:
        return {"session": None}

    return {
        "session": {
            "id": session["id"],
            "share_token": session["share_token"],
            "share_url": f"http://localhost:3000/track/{session['share_token']}",
            "created_at": session["created_at"],
        }
    }

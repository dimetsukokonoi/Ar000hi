"""Ride chat permissions, rate limits and persistence."""
import uuid
import time
import threading
from datetime import datetime
from app.models.database import get_db

_MAX_MSGS_PER_10S = 20
_spam: dict[str, list[float]] = {}
_spam_lock = threading.Lock()


def _allow_message(user_id: str) -> bool:
    """Return True if the user is under the send rate cap; else False."""
    now = time.time()
    with _spam_lock:
        stamps = [t for t in _spam.get(user_id, []) if now - t < 10]
        if len(stamps) >= _MAX_MSGS_PER_10S:
            return False
        stamps.append(now)
        _spam[user_id] = stamps
        return True


def _is_participant(conn, ride_id: str, user_id: str) -> bool:
    ride = conn.execute("SELECT driver_id FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if ride and ride["driver_id"] == user_id:
        return True
    row = conn.execute(
        """SELECT id FROM ride_passengers
           WHERE ride_id = ? AND passenger_id = ? AND status IN ('accepted', 'completed')""",
        (ride_id, user_id)
    ).fetchone()
    return row is not None


def sender_for_ride(ride_id: str, user_id: str) -> str | None:
    conn = get_db()
    if not _is_participant(conn, ride_id, user_id):
        conn.close()
        return None
    user = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user["name"] if user else "Unknown"


def save_message(ride_id: str, user_id: str, sender_name: str, message: str) -> dict:
    message = message[:500]
    msg_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO chat_messages (id, ride_id, sender_id, message, created_at) VALUES (?, ?, ?, ?, ?)",
        (msg_id, ride_id, user_id, message, created_at),
    )
    conn.commit()
    conn.close()
    return {
        "id": msg_id, "ride_id": ride_id, "sender_id": user_id,
        "sender_name": sender_name, "message": message, "created_at": created_at,
    }

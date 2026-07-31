"""
Arooohi Backend — Ride Chat Routes
Feature 15: Ride Chat (In-App Messaging)  (Ornab)
WebSocket endpoint for real-time messaging (SRS 3.3.4) + DB persistence.
Only the ride driver and accepted passengers may join a conversation.

Improvements in this pass:
- Per-user message rate limiting (spam guard) — max N messages per second.
- Message length capped at 500 chars.
"""
import uuid
import json
import time
import threading
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.database import get_db
from app.auth import decode_token

router = APIRouter()

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


class ConnectionManager:
    """Tracks live WebSocket connections per ride_id."""

    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, ride_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(ride_id, []).append(websocket)

    def disconnect(self, ride_id: str, websocket: WebSocket):
        if ride_id in self.active:
            self.active[ride_id] = [w for w in self.active[ride_id] if w is not websocket]
            if not self.active[ride_id]:
                del self.active[ride_id]

    async def broadcast(self, ride_id: str, payload: dict):
        if ride_id not in self.active:
            return
        for ws in list(self.active[ride_id]):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                self.disconnect(ride_id, ws)


manager = ConnectionManager()


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


@router.websocket("/chat/{ride_id}")
async def ride_chat_ws(websocket: WebSocket, ride_id: str):
    """Live ride chat. Connect as: ws://host/ws/chat/{ride_id}?token=<JWT>"""
    token = websocket.query_params.get("token", "")
    try:
        payload = decode_token(token)
    except Exception:
        await websocket.accept()
        await websocket.close(code=4401)
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.accept()
        await websocket.close(code=4401)
        return

    conn = get_db()
    if not _is_participant(conn, ride_id, user_id):
        conn.close()
        await websocket.accept()
        await websocket.close(code=4403)
        return
    user = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    sender_name = user["name"] if user else "Unknown"

    await manager.connect(ride_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                message = str(data.get("message", "")).strip()
            except json.JSONDecodeError:
                message = ""

            if not message:
                continue
            if len(message) > 500:
                message = message[:500]
            if not _allow_message(user_id):
                await websocket.send_text(json.dumps({
                    "error": "Slow down — message rate limit reached.",
                    "type": "rate_limited",
                }))
                continue

            msg_id = str(uuid.uuid4())
            created_at = datetime.utcnow().isoformat()

            db = get_db()
            db.execute(
                "INSERT INTO chat_messages (id, ride_id, sender_id, message, created_at) VALUES (?, ?, ?, ?, ?)",
                (msg_id, ride_id, user_id, message, created_at)
            )
            db.commit()
            db.close()

            payload = {
                "id": msg_id,
                "ride_id": ride_id,
                "sender_id": user_id,
                "sender_name": sender_name,
                "message": message,
                "created_at": created_at,
            }
            await manager.broadcast(ride_id, payload)
    except WebSocketDisconnect:
        manager.disconnect(ride_id, websocket)
    except Exception:
        manager.disconnect(ride_id, websocket)

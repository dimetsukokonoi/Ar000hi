"""
Arooohi Backend — Ride Chat Routes
Feature 15: Ride Chat (In-App Messaging)  (Ornab)
WebSocket endpoint for real-time messaging (SRS 3.3.4) + DB persistence.
Only the ride driver and accepted passengers may join a conversation.

Improvements in this pass:
- Per-user message rate limiting (spam guard) — max N messages per second.
- Message length capped at 500 chars.
"""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.models import chat as model
from app.models.identity import decode_token

router = APIRouter()


class ConnectionManager:
    """Tracks live WebSocket connections per ride_id."""

    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, ride_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(ride_id, []).append(websocket)

    def disconnect(self, ride_id: str, websocket: WebSocket):
        if ride_id in self.active:
            self.active[ride_id] = [
                w for w in self.active[ride_id] if w is not websocket
            ]
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

    sender_name = model.sender_for_ride(ride_id, user_id)
    if sender_name is None:
        await websocket.accept()
        await websocket.close(code=4403)
        return

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
            if not model._allow_message(user_id):
                # Spam guard exceeded (API.md: 20 msgs / 10 s) — close 4429 so the
                # client stops sending; the per-user counter persists across reconnects.
                await websocket.send_text(
                    json.dumps(
                        {
                            "error": "Slow down — message rate limit reached.",
                            "type": "rate_limited",
                        }
                    )
                )
                await websocket.close(code=4429)
                break

            payload = model.save_message(ride_id, user_id, sender_name, message)
            await manager.broadcast(ride_id, payload)
        manager.disconnect(ride_id, websocket)
    except WebSocketDisconnect:
        manager.disconnect(ride_id, websocket)
    except Exception:
        manager.disconnect(ride_id, websocket)

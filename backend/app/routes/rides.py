"""
Arooohi Backend — Rides Core Routes
(Ornab) Minimal ride lifecycle foundation needed by Ornab's features:
  - Ride Cost Splitter
  - Peak Hour Surge Indicator (consumes ride volume)
  - Ride Chat (ride-scoped conversations)
  - Eco/Footprint Tracker (distance + occupancy per completed ride)
NOTE: This is a MINIMAL ride model for demo purposes. Full matching/booking
(SRS Sprint 2) is a separate teammate module and can build on these tables.
"""
import uuid
import math
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.auth import get_current_user_id
from app.routes.surge import compute_current_multiplier

router = APIRouter()

# Small BRACU-area zone lookup used to estimate distance when GPS points are unavailable.
ZONES = {
    "gate 1": (23.7800, 90.4100), "gate 2": (23.7765, 90.4070), "gate 3": (23.7792, 90.4120),
    "library": (23.7781, 90.4042), "cafeteria": (23.7770, 90.4050), "cafe": (23.7770, 90.4050),
    "ub building": (23.7788, 90.4060), "ub": (23.7788, 90.4060), "residential": (23.7820, 90.4080),
    "residence": (23.7820, 90.4080), "mohakhali": (23.7700, 90.4020), "banani": (23.7760, 90.4100),
    "gulshan": (23.7900, 90.4100), "dhanmondi": (23.7450, 90.3800), "mirpur": (23.8100, 90.3500),
}

EARTH_RADIUS_KM = 6371.0


def _haversine_km(a: tuple, b: tuple) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _estimate_distance_km(source: str, destination: str) -> float:
    """Estimate distance from the zone lookup; fall back to a default for the demo."""
    s = ZONES.get(source.strip().lower())
    d = ZONES.get(destination.strip().lower())
    if s and d:
        return round(_haversine_km(s, d), 2)
    return 5.0  # default demo distance


class CreateRideRequest(BaseModel):
    source: str
    destination: str
    base_fare: float
    scheduled_at: str | None = None


class JoinRideRequest(BaseModel):
    seats: int = 1


class EndRideRequest(BaseModel):
    distance_km: float | None = None


@router.post("")
def create_ride(body: CreateRideRequest, user_id: str = Depends(get_current_user_id)):
    """Driver creates a new ride. (Demo: any verified user may create a ride.)"""
    conn = get_db()
    user = conn.execute("SELECT is_verified, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    if not user["is_verified"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Verify your BRACU email before creating rides")

    if body.base_fare <= 0:
        conn.close()
        raise HTTPException(status_code=400, detail="base_fare must be positive")

    # Capture the current surge multiplier so the cost splitter reflects live pricing.
    surge, _, _ = compute_current_multiplier(conn)

    ride_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO rides (id, driver_id, source, destination, base_fare, surge_multiplier, scheduled_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ride_id, user_id, body.source.strip(), body.destination.strip(),
         round(body.base_fare, 2), surge, body.scheduled_at)
    )
    conn.commit()
    conn.close()

    return {"message": "Ride created", "ride_id": ride_id, "status": "scheduled", "surge_multiplier": surge}


@router.post("/{ride_id}/join")
def join_ride(ride_id: str, body: JoinRideRequest, user_id: str = Depends(get_current_user_id)):
    """Rider requests a seat on a scheduled/active ride."""
    conn = get_db()
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride["status"] not in ("scheduled", "active"):
        conn.close()
        raise HTTPException(status_code=400, detail="Ride is not open for passengers")
    if ride["driver_id"] == user_id:
        conn.close()
        raise HTTPException(status_code=400, detail="You cannot join your own ride")

    existing = conn.execute(
        "SELECT id FROM ride_passengers WHERE ride_id = ? AND passenger_id = ? AND status IN ('requested','accepted')",
        (ride_id, user_id)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="You already have a pending/accepted seat on this ride")

    pid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO ride_passengers (id, ride_id, passenger_id, seats, status) VALUES (?, ?, ?, ?, 'requested')",
        (pid, ride_id, user_id, body.seats)
    )
    conn.commit()
    conn.close()
    return {"message": "Ride request sent", "passenger_id": pid, "status": "requested"}


@router.post("/{ride_id}/accept/{passenger_id}")
def accept_passenger(ride_id: str, passenger_id: str, user_id: str = Depends(get_current_user_id)):
    """Driver accepts a passenger's ride request."""
    conn = get_db()
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride["driver_id"] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Only the driver can accept passengers")

    result = conn.execute(
        "UPDATE ride_passengers SET status = 'accepted' WHERE id = ? AND ride_id = ?",
        (passenger_id, ride_id)
    )
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Ride request not found")
    return {"message": "Passenger accepted"}


@router.post("/{ride_id}/start")
def start_ride(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """Driver starts the ride."""
    conn = get_db()
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride["driver_id"] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Only the driver can start the ride")

    from datetime import datetime as dt
    now = dt.utcnow().isoformat()
    conn.execute(
        "UPDATE rides SET status = 'active', started_at = ? WHERE id = ?",
        (now, ride_id)
    )
    conn.commit()
    conn.close()
    return {"message": "Ride started", "status": "active"}


@router.post("/{ride_id}/end")
def end_ride(ride_id: str, body: EndRideRequest, user_id: str = Depends(get_current_user_id)):
    """Driver ends the ride — computes distance (tracking points or estimate) for eco tracking."""
    conn = get_db()
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride["driver_id"] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Only the driver can end the ride")

    distance = body.distance_km
    if distance is None:
        # Prefer distance travelled via GPS tracking points, else zone-based estimate.
        points = conn.execute(
            """SELECT lat, lng FROM tracking_points tp
               JOIN tracking_sessions ts ON tp.session_id = ts.id
               WHERE ts.user_id = ? AND ts.is_active = 0
               ORDER BY tp.created_at ASC LIMIT 2""",
            (user_id,)
        ).fetchall()
        if len(points) >= 2:
            distance = _haversine_km((points[0]["lat"], points[0]["lng"]),
                                     (points[-1]["lat"], points[-1]["lng"]))
        else:
            distance = _estimate_distance_km(ride["source"], ride["destination"])

    from datetime import datetime as dt
    conn.execute(
        """UPDATE rides SET status = 'completed', distance_km = ?, ended_at = ? WHERE id = ?""",
        (round(distance, 2), dt.utcnow().isoformat(), ride_id)
    )
    conn.execute(
        "UPDATE ride_passengers SET status = 'completed' WHERE ride_id = ? AND status = 'accepted'",
        (ride_id,)
    )
    conn.commit()
    conn.close()
    return {"message": "Ride completed", "distance_km": round(distance, 2)}


@router.get("")
def list_rides(user_id: str = Depends(get_current_user_id)):
    """List rides: mine (as driver/passenger) + other open rides available to join."""
    conn = get_db()

    mine = conn.execute(
        """SELECT r.*, u.name AS driver_name, u.id AS driver_id
           FROM rides r JOIN users u ON r.driver_id = u.id
           WHERE r.driver_id = ?
              OR r.id IN (SELECT ride_id FROM ride_passengers WHERE passenger_id = ?)
           ORDER BY r.created_at DESC""",
        (user_id, user_id)
    ).fetchall()

    available = conn.execute(
        """SELECT r.*, u.name AS driver_name, u.id AS driver_id
           FROM rides r JOIN users u ON r.driver_id = u.id
           WHERE r.driver_id != ?
             AND r.status IN ('scheduled', 'active')
             AND r.id NOT IN (SELECT ride_id FROM ride_passengers WHERE passenger_id = ?)
           ORDER BY r.created_at DESC""",
        (user_id, user_id)
    ).fetchall()
    conn.close()

    def _ser(ride):
        return {
            "id": ride["id"],
            "driver_id": ride["driver_id"],
            "driver_name": ride["driver_name"],
            "source": ride["source"],
            "destination": ride["destination"],
            "status": ride["status"],
            "distance_km": ride["distance_km"],
            "base_fare": ride["base_fare"],
            "surge_multiplier": ride["surge_multiplier"],
            "scheduled_at": ride["scheduled_at"],
            "started_at": ride["started_at"],
            "ended_at": ride["ended_at"],
            "created_at": ride["created_at"],
        }

    return {
        "mine": [_ser(r) for r in mine],
        "available": [_ser(r) for r in available],
    }


@router.get("/{ride_id}")
def get_ride(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """Ride detail including passengers (participants only)."""
    conn = get_db()
    ride = conn.execute(
        """SELECT r.*, u.name AS driver_name FROM rides r
           JOIN users u ON r.driver_id = u.id WHERE r.id = ?""",
        (ride_id,)
    ).fetchone()
    if not ride:
        conn.close()
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride["driver_id"] != user_id:
        participant = conn.execute(
            "SELECT id FROM ride_passengers WHERE ride_id = ? AND passenger_id = ?",
            (ride_id, user_id)
        ).fetchone()
        if not participant:
            conn.close()
            raise HTTPException(status_code=403, detail="Only ride participants can view this ride")

    passengers = conn.execute(
        """SELECT rp.id, rp.passenger_id, rp.seats, rp.status, u.name AS passenger_name
           FROM ride_passengers rp JOIN users u ON rp.passenger_id = u.id
           WHERE rp.ride_id = ?""",
        (ride_id,)
    ).fetchall()
    conn.close()

    return {
        "id": ride["id"],
        "driver_id": ride["driver_id"],
        "driver_name": ride["driver_name"],
        "source": ride["source"],
        "destination": ride["destination"],
        "status": ride["status"],
        "distance_km": ride["distance_km"],
        "base_fare": ride["base_fare"],
        "surge_multiplier": ride["surge_multiplier"],
        "scheduled_at": ride["scheduled_at"],
        "started_at": ride["started_at"],
        "ended_at": ride["ended_at"],
        "created_at": ride["created_at"],
        "passengers": [
            {
                "id": p["id"],
                "passenger_id": p["passenger_id"],
                "passenger_name": p["passenger_name"],
                "seats": p["seats"],
                "status": p["status"],
            }
            for p in passengers
        ],
    }


@router.get("/{ride_id}/split")
def ride_cost_split(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """Ride Cost Splitter — total = base_fare x surge; split evenly among accepted passengers.
    (SRS Feature 5)"""
    conn = get_db()
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise HTTPException(status_code=404, detail="Ride not found")

    accepted = conn.execute(
        """SELECT u.name FROM ride_passengers rp JOIN users u ON rp.passenger_id = u.id
           WHERE rp.ride_id = ? AND rp.status IN ('accepted', 'completed')""",
        (ride_id,)
    ).fetchall()
    conn.close()

    total = round(ride["base_fare"] * ride["surge_multiplier"], 2)
    passenger_count = len(accepted)
    per_person = round(total / passenger_count, 2) if passenger_count > 0 else None

    return {
        "ride_id": ride_id,
        "source": ride["source"],
        "destination": ride["destination"],
        "base_fare": ride["base_fare"],
        "surge_multiplier": ride["surge_multiplier"],
        "total": total,
        "passenger_count": passenger_count,
        "per_person": per_person,
        "breakdown": [
            {"passenger": p["name"], "share": per_person if per_person else 0}
            for p in accepted
        ],
    }


@router.get("/{ride_id}/messages")
def get_ride_messages(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """Ride Chat history (participants only)."""
    conn = get_db()
    ride = conn.execute("SELECT driver_id FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride["driver_id"] != user_id:
        participant = conn.execute(
            "SELECT id FROM ride_passengers WHERE ride_id = ? AND passenger_id = ? AND status IN ('accepted','completed')",
            (ride_id, user_id)
        ).fetchone()
        if not participant:
            conn.close()
            raise HTTPException(status_code=403, detail="Only ride participants can view the chat")

    messages = conn.execute(
        """SELECT cm.id, cm.sender_id, cm.message, cm.created_at, u.name AS sender_name
           FROM chat_messages cm JOIN users u ON cm.sender_id = u.id
           WHERE cm.ride_id = ? ORDER BY cm.created_at ASC""",
        (ride_id,)
    ).fetchall()
    conn.close()

    return [
        {
            "id": m["id"],
            "sender_id": m["sender_id"],
            "sender_name": m["sender_name"],
            "message": m["message"],
            "created_at": m["created_at"],
        }
        for m in messages
    ]

"""
Arooohi Backend — Rides Core Routes
(Ornab) Minimal ride lifecycle foundation needed by Ornab's features:
  - Ride Cost Splitter
  - Peak Hour Surge Indicator (consumes ride volume)
  - Ride Chat (ride-scoped conversations)
  - Eco/Footprint Tracker (distance + occupancy per completed ride)
NOTE: This is a MINIMAL ride model for demo purposes. Full matching/booking
(SRS Sprint 2) is a separate teammate module and can build on these tables.

Improvements in this pass (cross-agent, 2026-07-31):
- Ride Cost Splitter: seat-aware split + whole-taka largest-remainder rounding so
  the per-person shares always sum exactly to the total fare (PROJECT_PLAN §6.2).
- Join: seat count validated against ride capacity (`total_seats`).
- end_ride: distance now measured over the FULL path of the rider's most recent
  inactive tracking session (sum of consecutive legs), not the first 2 points of
  any old session.
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


def _path_length_km(points) -> float:
    """Sum of consecutive haversine legs over an ordered list of (lat, lng) points."""
    pts = [(p["lat"], p["lng"]) for p in points]
    if len(pts) < 2:
        return 0.0
    return sum(_haversine_km(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


class CreateRideRequest(BaseModel):
    source: str
    destination: str
    base_fare: float
    total_seats: int = 4
    scheduled_at: str | None = None


class JoinRideRequest(BaseModel):
    seats: int = 1

    def model_post_init(self, __context):
        if self.seats < 1:
            raise ValueError("seats must be at least 1")


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

    if body.total_seats < 1 or body.total_seats > 10:
        conn.close()
        raise HTTPException(status_code=400, detail="total_seats must be between 1 and 10")

    # Capture the current surge multiplier so the cost splitter reflects live pricing.
    surge, _, _ = compute_current_multiplier(conn)

    ride_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO rides (id, driver_id, source, destination, base_fare, surge_multiplier, total_seats, scheduled_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (ride_id, user_id, body.source.strip(), body.destination.strip(),
         round(body.base_fare, 2), surge, body.total_seats, body.scheduled_at)
    )
    conn.commit()
    conn.close()

    return {"message": "Ride created", "ride_id": ride_id, "status": "scheduled", "surge_multiplier": surge, "total_seats": body.total_seats}


@router.post("/{ride_id}/join")
def join_ride(ride_id: str, body: JoinRideRequest, user_id: str = Depends(get_current_user_id)):
    """Rider requests a seat on a scheduled/active ride.

    Improvement note:
    - Seat requests are now constrained to a positive seat count to keep the rider-side ride sharing flow consistent with the split-cost model.
    """
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
    if body.seats < 1:
        conn.close()
        raise HTTPException(status_code=400, detail="seats must be at least 1")

    # Capacity check: seats already taken (accepted/requested) + this request.
    taken = conn.execute(
        """SELECT COALESCE(SUM(seats), 0) AS s FROM ride_passengers
           WHERE ride_id = ? AND status IN ('requested', 'accepted')""",
        (ride_id,)
    ).fetchone()["s"]
    capacity = ride["total_seats"] or 4
    if taken + body.seats > capacity:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Not enough seats. This ride has {capacity} seats and {taken} are taken."
        )

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
        # Fix (§6.2): use the driver's MOST RECENT inactive session and sum the FULL
        # path length (all legs), instead of the gap between the 2 oldest points of
        # any old session.
        session = conn.execute(
            """SELECT id FROM tracking_sessions
               WHERE user_id = ? AND is_active = 0
               ORDER BY created_at DESC LIMIT 1""",
            (user_id,)
        ).fetchone()
        points = []
        if session:
            points = conn.execute(
                "SELECT lat, lng FROM tracking_points WHERE session_id = ? ORDER BY created_at ASC",
                (session["id"],)
            ).fetchall()
        path = _path_length_km(points)
        distance = path if path > 0.0 else _estimate_distance_km(ride["source"], ride["destination"])

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
            "total_seats": ride["total_seats"],
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
        "total_seats": ride["total_seats"],
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
    """Ride Cost Splitter — total = base_fare x surge; split by SEATS among accepted
    passengers, with whole-taka largest-remainder rounding so shares sum exactly
    to `total`.

    Improvement note:
    - Access is now restricted to the driver or an accepted ride participant.
    - A passenger booking N seats pays N shares (seat-aware split).
    - Largest-remainder pass fixes the rounding drift from the old
      `round(total / n, 2)` per person (PROJECT_PLAN.md §6.2).
    (SRS Feature 5)"""
    conn = get_db()
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise HTTPException(status_code=404, detail="Ride not found")

    is_driver = ride["driver_id"] == user_id
    participant = conn.execute(
        "SELECT id FROM ride_passengers WHERE ride_id = ? AND passenger_id = ? AND status IN ('accepted', 'completed')",
        (ride_id, user_id)
    ).fetchone()
    if not is_driver and not participant:
        conn.close()
        raise HTTPException(status_code=403, detail="Only ride participants can view fare split details")

    accepted = conn.execute(
        """SELECT rp.id, rp.passenger_id, rp.seats, u.name
           FROM ride_passengers rp JOIN users u ON rp.passenger_id = u.id
           WHERE rp.ride_id = ? AND rp.status IN ('accepted', 'completed')""",
        (ride_id,)
    ).fetchall()
    conn.close()

    total = round(ride["base_fare"] * ride["surge_multiplier"], 2)
    seat_weights = [max(int(r["seats"]), 1) for r in accepted]
    total_seats = sum(seat_weights)
    seat_shares = _split_total(total, total_seats) if total_seats > 0 else []

    breakdown = []
    share_idx = 0
    for r in accepted:
        weight = max(int(r["seats"]), 1)
        share = round(sum(seat_shares[share_idx:share_idx + weight]), 2)
        share_idx += weight
        breakdown.append({"passenger": r["name"], "seats": weight, "share": share})

    return {
        "ride_id": ride_id,
        "source": ride["source"],
        "destination": ride["destination"],
        "base_fare": ride["base_fare"],
        "surge_multiplier": ride["surge_multiplier"],
        "total": total,
        "total_seats": total_seats,
        "passenger_count": len(accepted),
        "per_seat": round(seat_shares[0], 2) if seat_shares else None,
        "breakdown": breakdown,
    }


def _split_total(total: float, parts: int) -> list[float]:
    """Largest-remainder split at paisa (0.01 taka) resolution so the parts sum
    EXACTLY to `total`. Fixes the rounding drift of naive `round(total / n, 2)`.
    Example: 130 / 3 -> [43.34, 43.33, 43.33] (sums to 130.00)."""
    if parts <= 0:
        return []
    total_paisa = round(total * 100)
    base = total_paisa // parts
    remainder = total_paisa - base * parts
    shares = [round(base / 100.0, 2)] * parts
    for i in range(remainder):
        shares[i] = round((base + 1) / 100.0, 2)
    return shares


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

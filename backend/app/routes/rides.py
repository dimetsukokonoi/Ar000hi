"""
Arooohi Backend — Rides Core & Campus Smart Matching Routes
Features implemented:
  - Feature 3: Female-Only Ride Mode (gender-gated creation, joining, and filtering)
  - Feature 6: Campus Zone Smart Matching (route stops, zone proximity, time-flex matching)
  - Feature 8: Scheduled Ride Booking (ISO scheduling, class-time presets, time window matching)
  - Feature 14: Dynamic Cost Splitter (seat-aware largest-remainder split)
  - Feature 15: Ride Chat (WebSocket & message history)
  - Feature 19: Multi-Stop Ride Support (intermediate stops, passenger-specific pickup/dropoff, stop progress)
  - Feature 20: Campus Pickup Hotspots (categorized campus gates, academic plazas, transit hubs)
"""
import uuid
import math
from datetime import datetime as dt, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from app.database import get_db
from app.auth import get_current_user_id
from app.routes.surge import compute_current_multiplier
from app import wallet_service as ws

router = APIRouter()

HOTSPOTS = [
    {
        "id": "gate 1",
        "name": "Gate 1 (Main Entrance)",
        "category": "campus_gate",
        "lat": 23.7800,
        "lng": 90.4100,
        "description": "BRACU Main Gate 1 & Security Checkpoint",
        "popular": True,
    },
    {
        "id": "gate 2",
        "name": "Gate 2 (West Wing)",
        "category": "campus_gate",
        "lat": 23.7765,
        "lng": 90.4070,
        "description": "West Gate pickup area near cafeteria",
        "popular": False,
    },
    {
        "id": "gate 3",
        "name": "Gate 3 (East Wing)",
        "category": "campus_gate",
        "lat": 23.7792,
        "lng": 90.4120,
        "description": "East Gate & Bike Parking zone",
        "popular": False,
    },
    {
        "id": "library",
        "name": "Ayesha Abed Library",
        "category": "academic",
        "lat": 23.7781,
        "lng": 90.4042,
        "description": "Central Library & Study Plaza",
        "popular": True,
    },
    {
        "id": "cafeteria",
        "name": "Main Cafeteria & Lounge",
        "category": "academic",
        "lat": 23.7770,
        "lng": 90.4050,
        "description": "Cafeteria outdoor plaza & student hangout",
        "popular": True,
    },
    {
        "id": "ub building",
        "name": "UB Building (UB01-UB07)",
        "category": "academic",
        "lat": 23.7788,
        "lng": 90.4060,
        "description": "University Building classrooms & labs",
        "popular": True,
    },
    {
        "id": "residential",
        "name": "Residential Campus Hub",
        "category": "residential",
        "lat": 23.7820,
        "lng": 90.4080,
        "description": "Student dormitories and housing area",
        "popular": False,
    },
    {
        "id": "mohakhali",
        "name": "Mohakhali Wireless Gate",
        "category": "transit_hub",
        "lat": 23.7700,
        "lng": 90.4020,
        "description": "Major transit point connecting to BRACU",
        "popular": True,
    },
    {
        "id": "banani",
        "name": "Banani Road 11 / Station",
        "category": "transit_hub",
        "lat": 23.7760,
        "lng": 90.4100,
        "description": "Banani commercial and pickup zone",
        "popular": True,
    },
    {
        "id": "gulshan",
        "name": "Gulshan-1 Circle",
        "category": "transit_hub",
        "lat": 23.7900,
        "lng": 90.4100,
        "description": "Gulshan roundabout & bus stoppage",
        "popular": True,
    },
    {
        "id": "dhanmondi",
        "name": "Dhanmondi Hub (Road 27)",
        "category": "transit_hub",
        "lat": 23.7450,
        "lng": 90.3800,
        "description": "Dhanmondi student carpool hub",
        "popular": False,
    },
    {
        "id": "mirpur",
        "name": "Mirpur 10 Circle (Metro)",
        "category": "transit_hub",
        "lat": 23.8100,
        "lng": 90.3500,
        "description": "Mirpur metro rail & student transit hub",
        "popular": False,
    },
]

ZONES = {h["id"]: (h["lat"], h["lng"]) for h in HOTSPOTS}
ZONES["cafe"] = ZONES["cafeteria"]
ZONES["ub"] = ZONES["ub building"]
ZONES["residence"] = ZONES["residential"]

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


@router.get("/hotspots")
def get_hotspots():
    """Returns categorized campus pickup hotspots and transit points."""
    return HOTSPOTS


class CreateRideRequest(BaseModel):
    source: str
    destination: str
    base_fare: float
    total_seats: int = 4
    scheduled_at: str | None = None
    female_only: bool = False
    stops: list[str] = []


class JoinRideRequest(BaseModel):
    seats: int = 1
    pickup_stop: str | None = None
    dropoff_stop: str | None = None

    def model_post_init(self, __context):
        if self.seats < 1:
            raise ValueError("seats must be at least 1")


class EndRideRequest(BaseModel):
    distance_km: float | None = None


class UpdateStopStatusRequest(BaseModel):
    status: str  # 'pending', 'reached', 'departed'


@router.post("")
def create_ride(body: CreateRideRequest, user_id: str = Depends(get_current_user_id)):
    """Driver creates a new ride with multi-stop and scheduling support."""
    conn = get_db()
    user = conn.execute("SELECT is_verified, role, gender FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    if not user["is_verified"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Verify your BRACU email before creating rides")

    if body.female_only and user["gender"] != "female":
        conn.close()
        raise HTTPException(status_code=403, detail="Only female drivers can create female-only rides")

    if body.base_fare <= 0:
        conn.close()
        raise HTTPException(status_code=400, detail="base_fare must be positive")

    if body.total_seats < 1 or body.total_seats > 10:
        conn.close()
        raise HTTPException(status_code=400, detail="total_seats must be between 1 and 10")

    if body.scheduled_at:
        try:
            # Allow ISO formats
            parsed = dt.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
            # If naive, compare with naive utcnow
            if parsed.tzinfo is None and parsed < dt.utcnow():
                conn.close()
                raise HTTPException(status_code=400, detail="Scheduled time must be in the future")
        except ValueError:
            pass

    surge, _, _ = compute_current_multiplier(conn)

    ride_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO rides (id, driver_id, source, destination, base_fare, surge_multiplier, total_seats, scheduled_at, female_only)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ride_id, user_id, body.source.strip(), body.destination.strip(),
         round(body.base_fare, 2), surge, body.total_seats, body.scheduled_at, int(body.female_only))
    )
    for idx, stop in enumerate(body.stops):
        if stop.strip():
            conn.execute(
                "INSERT INTO ride_stops (id, ride_id, sequence, place, status) VALUES (?, ?, ?, ?, 'pending')",
                (str(uuid.uuid4()), ride_id, idx, stop.strip())
            )
    conn.commit()
    conn.close()

    return {"message": "Ride created", "ride_id": ride_id, "status": "scheduled", "surge_multiplier": surge, "total_seats": body.total_seats}


@router.post("/{ride_id}/join")
def join_ride(ride_id: str, body: JoinRideRequest, user_id: str = Depends(get_current_user_id)):
    """Rider requests a seat on a ride, optionally specifying their pickup and drop-off stops."""
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

    user = conn.execute("SELECT gender FROM users WHERE id = ?", (user_id,)).fetchone()
    if ride["female_only"] and user["gender"] != "female":
        conn.close()
        raise HTTPException(status_code=403, detail="This is a female-only ride")

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

    # Feature 9: prepaid wallets — check affordability BEFORE the seat is held.
    projected = ws.projected_share(conn, ride, body.seats)
    balance = ws.balance_of(conn, user_id)
    if balance < projected:
        conn.close()
        raise HTTPException(
            status_code=402,
            detail=(f"Insufficient wallet balance. This ride costs about "
                    f"{projected:.2f} BDT and you have {balance:.2f} BDT. "
                    f"Top up {projected - balance:.2f} BDT to join."),
        )

    stops = [r["place"].lower() for r in conn.execute("SELECT place FROM ride_stops WHERE ride_id = ?", (ride_id,)).fetchall()]
    valid_places = {ride["source"].lower(), ride["destination"].lower(), *stops}

    pickup = body.pickup_stop.strip() if body.pickup_stop else ride["source"]
    dropoff = body.dropoff_stop.strip() if body.dropoff_stop else ride["destination"]

    pid = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO ride_passengers (id, ride_id, passenger_id, seats, pickup_stop, dropoff_stop, status)
           VALUES (?, ?, ?, ?, ?, ?, 'requested')""",
        (pid, ride_id, user_id, body.seats, pickup, dropoff)
    )
    conn.commit()
    conn.close()
    return {
        "message": "Ride request sent",
        "passenger_id": pid,
        "status": "requested",
        "pickup_stop": pickup,
        "dropoff_stop": dropoff,
        "seats": body.seats,
        "estimated_share": projected,
        "wallet_balance": balance,
    }


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


@router.post("/{ride_id}/stops/{stop_id}/status")
def update_stop_status(ride_id: str, stop_id: str, body: UpdateStopStatusRequest, user_id: str = Depends(get_current_user_id)):
    """Driver updates progress of a stop (pending, reached, departed)."""
    if body.status not in ("pending", "reached", "departed"):
        raise HTTPException(status_code=400, detail="Status must be pending, reached, or departed")

    conn = get_db()
    ride = conn.execute("SELECT driver_id FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride["driver_id"] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Only the driver can update stop progress")

    res = conn.execute(
        "UPDATE ride_stops SET status = ? WHERE id = ? AND ride_id = ?",
        (body.status, stop_id, ride_id)
    )
    conn.commit()
    conn.close()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Stop not found for this ride")
    return {"message": f"Stop status updated to {body.status}", "stop_id": stop_id, "status": body.status}


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

    conn.execute(
        """UPDATE rides SET status = 'completed', distance_km = ?, ended_at = ? WHERE id = ?""",
        (round(distance, 2), dt.utcnow().isoformat(), ride_id)
    )
    conn.execute(
        "UPDATE ride_passengers SET status = 'completed' WHERE ride_id = ? AND status = 'accepted'",
        (ride_id,)
    )
    conn.commit()

    # Feature 9: settle the fare from rider wallets into the driver's wallet.
    # Idempotent — re-ending a ride will not charge anyone twice.
    settlement = {"status": "skipped"}
    try:
        ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
        settlement = ws.settle_ride(conn, ride)
    except Exception as e:
        # Never fail the ride completion because settlement had a problem; the
        # ride is over either way and the fare can be reconciled afterwards.
        settlement = {"status": "error", "detail": str(e)}
    conn.close()

    return {
        "message": "Ride completed",
        "distance_km": round(distance, 2),
        "settlement": settlement,
    }


@router.get("/match")
def match_rides(
    source: str | None = None,
    destination: str | None = None,
    scheduled_date: str | None = None,
    scheduled_time: str | None = None,
    female_only: bool = False,
    user_id: str = Depends(get_current_user_id)
):
    """Smart Matching Algorithm:
    Matches riders with open rides heading to their destination or passing through their intermediate stops.
    Supports proximity zone matching, class schedule time-flex matching, and female-only filtering.
    """
    conn = get_db()
    user = conn.execute("SELECT gender FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    if female_only and user["gender"] != "female":
        conn.close()
        raise HTTPException(status_code=403, detail="Female-only matching is available for female students only")

    # Fetch available scheduled/active rides
    rides = conn.execute(
        """SELECT r.*, u.name AS driver_name, u.gender AS driver_gender
           FROM rides r JOIN users u ON r.driver_id = u.id
           WHERE r.driver_id != ?
             AND r.status IN ('scheduled', 'active')
             AND r.id NOT IN (SELECT ride_id FROM ride_passengers WHERE passenger_id = ?)
             AND (r.female_only = 0 OR ? = 'female')
           ORDER BY r.created_at DESC""",
        (user_id, user_id, user["gender"])
    ).fetchall()

    stops = conn.execute("SELECT id, ride_id, sequence, place, status FROM ride_stops ORDER BY sequence ASC").fetchall()
    ride_stops_map = {}
    for s in stops:
        ride_stops_map.setdefault(s["ride_id"], []).append({
            "id": s["id"], "sequence": s["sequence"], "place": s["place"], "status": s["status"]
        })

    passengers = conn.execute(
        """SELECT ride_id, SUM(seats) as taken FROM ride_passengers
           WHERE status IN ('requested', 'accepted') GROUP BY ride_id"""
    ).fetchall()
    taken_map = {p["ride_id"]: p["taken"] for p in passengers}

    conn.close()

    norm_src = source.strip().lower() if source else ""
    norm_dst = destination.strip().lower() if destination else ""

    matched_results = []

    for r in rides:
        ride_id = r["id"]
        total_seats = r["total_seats"] or 4
        taken_seats = taken_map.get(ride_id, 0)
        available_seats = max(0, total_seats - taken_seats)
        if available_seats <= 0:
            continue

        if female_only and not r["female_only"]:
            continue

        ride_src = r["source"].strip().lower()
        ride_dst = r["destination"].strip().lower()
        r_stops = ride_stops_map.get(ride_id, [])
        stop_names = [s["place"].strip().lower() for s in r_stops]

        score = 0
        reasons = []

        # Source / Pickup scoring
        if not norm_src:
            score += 40
        elif norm_src == ride_src or norm_src in ride_src or ride_src in norm_src:
            score += 50
            reasons.append("Exact Pickup Point")
        else:
            # Proximity check
            s_coord = ZONES.get(norm_src)
            rs_coord = ZONES.get(ride_src)
            if s_coord and rs_coord:
                dist = _haversine_km(s_coord, rs_coord)
                if dist <= 1.5:
                    score += 35
                    reasons.append(f"Nearby Pickup Zone ({round(dist, 1)}km)")
                else:
                    score += 0
            else:
                score += 10

        # Destination / Drop-off scoring (checks main destination + intermediate stops)
        if not norm_dst:
            score += 40
        elif norm_dst == ride_dst or norm_dst in ride_dst or ride_dst in norm_dst:
            score += 50
            reasons.append("Direct Destination Match")
        elif norm_dst in stop_names:
            score += 45
            matched_stop = next((s["place"] for s in r_stops if s["place"].strip().lower() == norm_dst), norm_dst)
            reasons.append(f"Multi-Stop Route Match: {matched_stop}")
        else:
            # Proximity check across destination + all stops
            d_coord = ZONES.get(norm_dst)
            best_dist = 999.0
            best_place = ""
            if d_coord:
                for place_name in [ride_dst, *stop_names]:
                    p_coord = ZONES.get(place_name)
                    if p_coord:
                        d = _haversine_km(d_coord, p_coord)
                        if d < best_dist:
                            best_dist = d
                            best_place = place_name
                if best_dist <= 1.5:
                    score += 35
                    reasons.append(f"Near Drop-off ({round(best_dist, 1)}km of {best_place.title()})")
                else:
                    score += 0
            else:
                score += 10

        # Time & Class Schedule scoring
        if scheduled_time or scheduled_date:
            if r["scheduled_at"]:
                try:
                    r_dt = dt.fromisoformat(r["scheduled_at"].replace("Z", "+00:00"))
                    if scheduled_time:
                        # Extract hour:minute
                        req_parts = scheduled_time.split(":")
                        if len(req_parts) == 2:
                            req_h, req_m = int(req_parts[0]), int(req_parts[1])
                            diff_mins = abs((r_dt.hour * 60 + r_dt.minute) - (req_h * 60 + req_m))
                            if diff_mins <= 30:
                                score += 15
                                reasons.append(f"Class Time Match ({scheduled_time})")
                            elif diff_mins <= 60:
                                score += 8
                                reasons.append(f"Near Class Time (±{diff_mins}m)")
                            else:
                                score -= 10
                except Exception:
                    pass

        if bool(r["female_only"]):
            reasons.append("🌸 Female-Only Carpool")

        # Require a valid match score if user provided explicit filters
        if norm_src and norm_dst and score < 50:
            continue

        matched_results.append({
            "id": r["id"],
            "driver_id": r["driver_id"],
            "driver_name": r["driver_name"],
            "source": r["source"],
            "destination": r["destination"],
            "status": r["status"],
            "distance_km": r["distance_km"],
            "base_fare": r["base_fare"],
            "surge_multiplier": r["surge_multiplier"],
            "total_seats": total_seats,
            "available_seats": available_seats,
            "scheduled_at": r["scheduled_at"],
            "female_only": bool(r["female_only"]),
            "stops": r_stops,
            "match_score": min(100, score),
            "match_reasons": reasons if reasons else ["General Campus Route"],
        })

    matched_results.sort(key=lambda x: (x["match_score"], x["scheduled_at"] or ""), reverse=True)
    return matched_results


@router.get("")
def list_rides(
    female_only: bool = False,
    user_id: str = Depends(get_current_user_id)
):
    """List rides: mine (as driver/passenger) + open available rides."""
    conn = get_db()
    user = conn.execute("SELECT gender FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    mine = conn.execute(
        """SELECT r.*, u.name AS driver_name, u.id AS driver_id
           FROM rides r JOIN users u ON r.driver_id = u.id
           WHERE r.driver_id = ?
              OR r.id IN (SELECT ride_id FROM ride_passengers WHERE passenger_id = ?)
           ORDER BY r.created_at DESC""",
        (user_id, user_id)
    ).fetchall()

    avail_query = """SELECT r.*, u.name AS driver_name, u.id AS driver_id
           FROM rides r JOIN users u ON r.driver_id = u.id
           WHERE r.driver_id != ?
             AND r.status IN ('scheduled', 'active')
             AND r.id NOT IN (SELECT ride_id FROM ride_passengers WHERE passenger_id = ?)
             AND (r.female_only = 0 OR ? = 'female')"""
    params = [user_id, user_id, user["gender"]]

    if female_only:
        avail_query += " AND r.female_only = 1"

    avail_query += " ORDER BY r.created_at DESC"
    available = conn.execute(avail_query, params).fetchall()

    stops = conn.execute("SELECT id, ride_id, sequence, place, status FROM ride_stops ORDER BY sequence ASC").fetchall()
    ride_stops_map = {}
    for s in stops:
        ride_stops_map.setdefault(s["ride_id"], []).append({
            "id": s["id"], "sequence": s["sequence"], "place": s["place"], "status": s["status"]
        })

    passengers = conn.execute(
        """SELECT ride_id, SUM(seats) as taken FROM ride_passengers
           WHERE status IN ('requested', 'accepted') GROUP BY ride_id"""
    ).fetchall()
    taken_map = {p["ride_id"]: p["taken"] for p in passengers}

    conn.close()

    def _ser(ride):
        total_seats = ride["total_seats"] or 4
        taken = taken_map.get(ride["id"], 0)
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
            "total_seats": total_seats,
            "available_seats": max(0, total_seats - taken),
            "scheduled_at": ride["scheduled_at"],
            "started_at": ride["started_at"],
            "ended_at": ride["ended_at"],
            "created_at": ride["created_at"],
            "female_only": bool(ride["female_only"]),
            "stops": ride_stops_map.get(ride["id"], []),
        }

    return {
        "mine": [_ser(r) for r in mine],
        "available": [_ser(r) for r in available],
    }


@router.get("/{ride_id}")
def get_ride(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """Ride detail including passenger stops and multi-stop progress."""
    conn = get_db()
    ride = conn.execute(
        """SELECT r.*, u.name AS driver_name, u.gender AS driver_gender FROM rides r
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
        """SELECT rp.id, rp.passenger_id, rp.seats, rp.status, rp.pickup_stop, rp.dropoff_stop, u.name AS passenger_name, u.gender AS passenger_gender
           FROM ride_passengers rp JOIN users u ON rp.passenger_id = u.id
           WHERE rp.ride_id = ?""",
        (ride_id,)
    ).fetchall()

    stops = conn.execute(
        "SELECT id, sequence, place, status FROM ride_stops WHERE ride_id = ? ORDER BY sequence ASC",
        (ride_id,)
    ).fetchall()

    conn.close()

    total_seats = ride["total_seats"] or 4
    taken = sum(p["seats"] for p in passengers if p["status"] in ("requested", "accepted"))

    return {
        "id": ride["id"],
        "driver_id": ride["driver_id"],
        "driver_name": ride["driver_name"],
        "driver_gender": ride["driver_gender"],
        "source": ride["source"],
        "destination": ride["destination"],
        "status": ride["status"],
        "distance_km": ride["distance_km"],
        "base_fare": ride["base_fare"],
        "surge_multiplier": ride["surge_multiplier"],
        "total_seats": total_seats,
        "available_seats": max(0, total_seats - taken),
        "scheduled_at": ride["scheduled_at"],
        "started_at": ride["started_at"],
        "ended_at": ride["ended_at"],
        "created_at": ride["created_at"],
        "female_only": bool(ride["female_only"]),
        "stops": [
            {"id": s["id"], "sequence": s["sequence"], "place": s["place"], "status": s["status"]}
            for s in stops
        ],
        "passengers": [
            {
                "id": p["id"],
                "passenger_id": p["passenger_id"],
                "passenger_name": p["passenger_name"],
                "passenger_gender": p["passenger_gender"],
                "seats": p["seats"],
                "pickup_stop": p["pickup_stop"] or ride["source"],
                "dropoff_stop": p["dropoff_stop"] or ride["destination"],
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
    """
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
        """SELECT rp.id, rp.passenger_id, rp.seats, rp.pickup_stop, rp.dropoff_stop, u.name
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
        breakdown.append({
            "passenger": r["name"],
            "seats": weight,
            "share": share,
            "pickup_stop": r["pickup_stop"] or ride["source"],
            "dropoff_stop": r["dropoff_stop"] or ride["destination"]
        })

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

    Delegates to `wallet_service.split_total` so the fare the splitter DISPLAYS
    and the amount the wallet CHARGES can never diverge (Feature 9)."""
    return ws.split_total(total, parts)


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


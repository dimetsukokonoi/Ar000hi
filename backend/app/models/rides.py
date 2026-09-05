"""Rides model: business rules and persistence, independent of FastAPI."""
import uuid
import math
from datetime import datetime as dt, timedelta, timezone
from app.models.database import get_db
from app.models.surge import compute_current_multiplier
from app.models import ledger as ws
from app.schemas.rides import CreateRideRequest, JoinRideRequest, EndRideRequest, UpdateStopStatusRequest, CancelRideRequest
from app.models.errors import DomainError

HOTSPOTS = [
    # --- BRACU New Campus in Merul Badda ---
    {
        "id": "gate 1",
        "name": "Gate 1 (Main Entrance - Pragati Sarani)",
        "category": "campus_gate",
        "lat": 23.7745,
        "lng": 90.4255,
        "description": "BRACU Main Gate 1 & Front Plaza on Bir Uttam Rafiqul Islam Ave / Pragati Sarani",
        "popular": True,
    },
    {
        "id": "gate 2",
        "name": "Gate 2 (Hatirjheel / West Walkway)",
        "category": "campus_gate",
        "lat": 23.7741,
        "lng": 90.4245,
        "description": "West entrance facing Hatirjheel promenade and lake link road",
        "popular": True,
    },
    {
        "id": "gate 3",
        "name": "Gate 3 (Aftabnagar / South Gate)",
        "category": "campus_gate",
        "lat": 23.7738,
        "lng": 90.4262,
        "description": "South student drop-off & parking gate near Aftabnagar link",
        "popular": False,
    },
    # --- Surrounding Transit Hubs & Student Residential Areas ---
    {
        "id": "aftabnagar",
        "name": "Aftabnagar Main Gate (Block A)",
        "category": "transit_hub",
        "lat": 23.7730,
        "lng": 90.4280,
        "description": "Directly across Pragati Sarani — major student residential hub & EWU link",
        "popular": True,
    },
    {
        "id": "hatirjheel ghat",
        "name": "Hatirjheel Merul Badda Water Taxi Ghat",
        "category": "transit_hub",
        "lat": 23.7725,
        "lng": 90.4230,
        "description": "Water taxi terminal connecting to FDC, Niketan, Gulshan-1 & Rampura",
        "popular": True,
    },
    {
        "id": "rampura bridge",
        "name": "Rampura Bridge / DIT Road",
        "category": "transit_hub",
        "lat": 23.7650,
        "lng": 90.4240,
        "description": "Major bus junction connecting to Malibagh, Kakrail, and South Dhaka",
        "popular": True,
    },
    {
        "id": "banasree",
        "name": "Banasree (Block A / Rampura Link)",
        "category": "transit_hub",
        "lat": 23.7600,
        "lng": 90.4350,
        "description": "Key student residential area across Rampura canal",
        "popular": False,
    },
    {
        "id": "notun bazar",
        "name": "Notun Bazar / Madani Ave (100 Feet)",
        "category": "transit_hub",
        "lat": 23.7930,
        "lng": 90.4260,
        "description": "Major transit hub towards Baridhara, Kuril, and Purbachal 300ft",
        "popular": True,
    },
    {
        "id": "gulshan 1",
        "name": "Gulshan-1 Circle (via Police Plaza)",
        "category": "transit_hub",
        "lat": 23.7790,
        "lng": 90.4180,
        "description": "Connected via Gudara Ghat / Hatirjheel link road to Badda",
        "popular": True,
    },
    {
        "id": "gulshan 2",
        "name": "Gulshan-2 Circle",
        "category": "transit_hub",
        "lat": 23.7925,
        "lng": 90.4165,
        "description": "Diplomatic zone & transit corridor",
        "popular": False,
    },
    {
        "id": "mohakhali",
        "name": "Mohakhali Wireless / Old Campus Hub",
        "category": "transit_hub",
        "lat": 23.7775,
        "lng": 90.4050,
        "description": "Connecting to Old Mohakhali campus & Western Dhaka routes",
        "popular": True,
    },
    {
        "id": "kuril",
        "name": "Kuril Flyover / Bishwa Road",
        "category": "transit_hub",
        "lat": 23.8180,
        "lng": 90.4230,
        "description": "Gateway to Airport Road, Uttara, and North-Eastern universities",
        "popular": True,
    },
    {
        "id": "bashundhara",
        "name": "Bashundhara R/A Gate / Jamuna Future Park",
        "category": "transit_hub",
        "lat": 23.8150,
        "lng": 90.4250,
        "description": "Pragati Sarani northern carpool corridor",
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
# Common aliases and synonyms
ZONES["gate 1"] = (23.7745, 90.4255)
ZONES["gate 2"] = (23.7741, 90.4245)
ZONES["gate 3"] = (23.7738, 90.4262)
ZONES["main gate"] = (23.7745, 90.4255)
ZONES["cafe"] = (23.7744, 90.4251)
ZONES["cafeteria"] = (23.7744, 90.4251)
ZONES["food court"] = (23.7744, 90.4251)
ZONES["library"] = (23.7747, 90.4250)
ZONES["ayesha abed library"] = (23.7747, 90.4250)
ZONES["academic building"] = (23.7746, 90.4252)
ZONES["ub building"] = (23.7746, 90.4252)
ZONES["ub"] = (23.7746, 90.4252)
ZONES["auditorium"] = (23.7743, 90.4254)
ZONES["sports complex"] = (23.7749, 90.4253)
ZONES["gym"] = (23.7749, 90.4253)
ZONES["aftabnagar"] = (23.7730, 90.4280)
ZONES["hatirjheel"] = (23.7725, 90.4230)
ZONES["hatirjheel ghat"] = (23.7725, 90.4230)
ZONES["water taxi"] = (23.7725, 90.4230)
ZONES["rampura"] = (23.7650, 90.4240)
ZONES["rampura bridge"] = (23.7650, 90.4240)
ZONES["banasree"] = (23.7600, 90.4350)
ZONES["notun bazar"] = (23.7930, 90.4260)
ZONES["madani avenue"] = (23.7930, 90.4260)
ZONES["gulshan 1"] = (23.7790, 90.4180)
ZONES["gulshan 2"] = (23.7925, 90.4165)
ZONES["mohakhali"] = (23.7775, 90.4050)
ZONES["kuril"] = (23.8180, 90.4230)
ZONES["bashundhara"] = (23.8150, 90.4250)
ZONES["dhanmondi"] = (23.7450, 90.3800)
ZONES["mirpur"] = (23.8100, 90.3500)

# Logical campus zone clusters for smart matching
CAMPUS_CLUSTERS = {
    "badda_campus": {"gate 1", "gate 2", "gate 3", "main gate", "academic building", "library", "ayesha abed library", "cafeteria", "cafe", "food court", "auditorium", "sports complex", "gym", "ub building", "ub"},
    "aftabnagar_lake": {"aftabnagar", "hatirjheel", "hatirjheel ghat", "water taxi"},
    "rampura_banasree": {"rampura", "rampura bridge", "banasree"},
    "gulshan_corridor": {"gulshan 1", "gulshan 2", "police plaza"},
    "pragati_sarani_north": {"notun bazar", "madani avenue", "kuril", "bashundhara", "jamuna"},
    "mohakhali_link": {"mohakhali", "old campus"},
    "dhanmondi_hub": {"dhanmondi"},
    "mirpur_hub": {"mirpur"},
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


def get_hotspots():
    """Returns categorized campus pickup hotspots and transit points."""
    return HOTSPOTS


def create_ride(body: CreateRideRequest, user_id: str):
    """Driver creates a new ride with multi-stop and scheduling support."""
    conn = get_db()
    user = conn.execute("SELECT is_verified, role, gender FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise DomainError(status_code=404, detail="User not found")
    if not user["is_verified"]:
        conn.close()
        raise DomainError(status_code=403, detail="Verify your BRACU email before creating rides")

    if body.female_only and user["gender"] != "female":
        conn.close()
        raise DomainError(status_code=403, detail="Only female drivers can create female-only rides")

    if body.base_fare <= 0:
        conn.close()
        raise DomainError(status_code=400, detail="base_fare must be positive")

    if body.total_seats < 1 or body.total_seats > 10:
        conn.close()
        raise DomainError(status_code=400, detail="total_seats must be between 1 and 10")

    if body.scheduled_at:
        try:
            # Accept standard ISO-8601 timestamps, including the UTC `Z` format
            # emitted by the dashboard. Treat a timezone-less legacy value as UTC.
            parsed = dt.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            conn.close()
            raise DomainError(status_code=400, detail="Scheduled time must be a valid ISO-8601 timestamp")

        if parsed <= dt.now(timezone.utc):
            conn.close()
            raise DomainError(status_code=400, detail="Scheduled time must be in the future")

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


def join_ride(ride_id: str, body: JoinRideRequest, user_id: str):
    """Rider requests a seat on a ride, optionally specifying their pickup and drop-off stops."""
    conn = get_db()
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise DomainError(status_code=404, detail="Ride not found")
    if ride["status"] not in ("scheduled", "active"):
        conn.close()
        raise DomainError(status_code=400, detail="Ride is not open for passengers")
    if ride["driver_id"] == user_id:
        conn.close()
        raise DomainError(status_code=400, detail="You cannot join your own ride")
    if body.seats < 1:
        conn.close()
        raise DomainError(status_code=400, detail="seats must be at least 1")

    user = conn.execute("SELECT gender FROM users WHERE id = ?", (user_id,)).fetchone()
    if ride["female_only"] and user["gender"] != "female":
        conn.close()
        raise DomainError(status_code=403, detail="This is a female-only ride")

    taken = conn.execute(
        """SELECT COALESCE(SUM(seats), 0) AS s FROM ride_passengers
           WHERE ride_id = ? AND status IN ('requested', 'accepted')""",
        (ride_id,)
    ).fetchone()["s"]
    capacity = ride["total_seats"] or 4
    if taken + body.seats > capacity:
        conn.close()
        raise DomainError(
            status_code=400,
            detail=f"Not enough seats. This ride has {capacity} seats and {taken} are taken."
        )

    existing = conn.execute(
        "SELECT id FROM ride_passengers WHERE ride_id = ? AND passenger_id = ? AND status IN ('requested','accepted')",
        (ride_id, user_id)
    ).fetchone()
    if existing:
        conn.close()
        raise DomainError(status_code=400, detail="You already have a pending/accepted seat on this ride")

    # A seat request is a reservation, not a wallet debit. Keeping the estimate
    # here lets the UI tell a rider whether they need to top up before the ride
    # ends, while still allowing a normal carpool request from a new ৳0 wallet.
    # The existing settlement flow remains the only place that debits a wallet.
    projected = ws.projected_share(conn, ride, body.seats)
    balance = ws.balance_of(conn, user_id)

    stop_rows = conn.execute(
        "SELECT sequence, place FROM ride_stops WHERE ride_id = ? ORDER BY sequence ASC",
        (ride_id,)
    ).fetchall()
    route_places = [ride["source"], *(stop["place"] for stop in stop_rows), ride["destination"]]
    route_positions = {}
    for position, place in enumerate(route_places):
        key = place.strip().casefold()
        if key and key not in route_positions:
            route_positions[key] = (position, place)

    pickup = (body.pickup_stop or "").strip() or ride["source"]
    dropoff = (body.dropoff_stop or "").strip() or ride["destination"]
    pickup_route = route_positions.get(pickup.casefold())
    dropoff_route = route_positions.get(dropoff.casefold())
    if not pickup_route or not dropoff_route:
        conn.close()
        raise DomainError(status_code=400, detail="Pickup and drop-off must be stops on this ride's route")
    if pickup_route[0] >= dropoff_route[0]:
        conn.close()
        raise DomainError(status_code=400, detail="Pickup must be before drop-off on this ride's route")

    # Store the canonical route names rather than a case variant sent by a client.
    pickup = pickup_route[1]
    dropoff = dropoff_route[1]

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
        "requires_topup": balance < projected,
        "topup_amount": round(max(0.0, projected - balance), 2),
    }


def accept_passenger(ride_id: str, passenger_id: str, user_id: str):
    """Driver accepts a passenger's ride request."""
    conn = get_db()
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise DomainError(status_code=404, detail="Ride not found")
    if ride["driver_id"] != user_id:
        conn.close()
        raise DomainError(status_code=403, detail="Only the driver can accept passengers")

    result = conn.execute(
        "UPDATE ride_passengers SET status = 'accepted' WHERE id = ? AND ride_id = ?",
        (passenger_id, ride_id)
    )
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise DomainError(status_code=404, detail="Ride request not found")
    return {"message": "Passenger accepted"}


def update_stop_status(ride_id: str, stop_id: str, body: UpdateStopStatusRequest, user_id: str):
    """Driver updates progress of a stop (pending, reached, departed)."""
    if body.status not in ("pending", "reached", "departed"):
        raise DomainError(status_code=400, detail="Status must be pending, reached, or departed")

    conn = get_db()
    ride = conn.execute("SELECT driver_id FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise DomainError(status_code=404, detail="Ride not found")
    if ride["driver_id"] != user_id:
        conn.close()
        raise DomainError(status_code=403, detail="Only the driver can update stop progress")

    res = conn.execute(
        "UPDATE ride_stops SET status = ? WHERE id = ? AND ride_id = ?",
        (body.status, stop_id, ride_id)
    )
    conn.commit()
    conn.close()
    if res.rowcount == 0:
        raise DomainError(status_code=404, detail="Stop not found for this ride")
    return {"message": f"Stop status updated to {body.status}", "stop_id": stop_id, "status": body.status}


def start_ride(ride_id: str, user_id: str):
    """Driver starts the ride."""
    conn = get_db()
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise DomainError(status_code=404, detail="Ride not found")
    if ride["driver_id"] != user_id:
        conn.close()
        raise DomainError(status_code=403, detail="Only the driver can start the ride")

    now = dt.utcnow().isoformat()
    conn.execute(
        "UPDATE rides SET status = 'active', started_at = ? WHERE id = ?",
        (now, ride_id)
    )
    conn.commit()
    conn.close()
    return {"message": "Ride started", "status": "active"}


def end_ride(ride_id: str, body: EndRideRequest, user_id: str):
    """Driver ends the ride — computes distance (tracking points or estimate) for eco tracking."""
    conn = get_db()
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise DomainError(status_code=404, detail="Ride not found")
    if ride["driver_id"] != user_id:
        conn.close()
        raise DomainError(status_code=403, detail="Only the driver can end the ride")

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


def match_rides(user_id: str, source: str | None=None, pickup: str | None=None, destination: str | None=None, dropoff: str | None=None, scheduled_date: str | None=None, scheduled_time: str | None=None, class_time: str | None=None, female_only: bool=False):
    """Smart Matching Algorithm:
    Matches riders with open rides heading to their destination or passing through their intermediate stops.
    Supports proximity zone matching, class schedule time-flex matching, and female-only filtering.
    """
    effective_source = (source or pickup or "").strip()
    effective_destination = (destination or dropoff or "").strip()
    effective_time = (scheduled_time or class_time or "").strip()

    conn = get_db()
    user = conn.execute("SELECT gender FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise DomainError(status_code=404, detail="User not found")

    if female_only and user["gender"] != "female":
        conn.close()
        raise DomainError(status_code=403, detail="Female-only matching is available for female students only")

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

    norm_src = effective_source.lower()
    norm_dst = effective_destination.lower()

    matched_results = []

    for r in rides:
        ride_id = r["id"]
        total_seats = r["total_seats"] or 4
        taken_seats = taken_map.get(ride_id, 0)
        available_seats = max(0, total_seats - taken_seats)
        if available_seats <= 0:
            continueDomainError: a model failure without a FastAPI dependency. controllers/errors.py translates its status/detail into the existing {"detail": "..."} error response.

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
            # Check cluster membership
            same_cluster = False
            for cluster_name, cluster_places in CAMPUS_CLUSTERS.items():
                if norm_src in cluster_places and ride_src in cluster_places:
                    same_cluster = True
                    break

            s_coord = ZONES.get(norm_src)
            rs_coord = ZONES.get(ride_src)
            if same_cluster or (s_coord and rs_coord and _haversine_km(s_coord, rs_coord) <= 0.4):
                score += 45
                reasons.append("Same Campus Pickup Zone")
            elif s_coord and rs_coord:
                dist = _haversine_km(s_coord, rs_coord)
                if dist <= 1.2:
                    score += 35
                    reasons.append(f"Nearby Pickup ({round(dist, 1)}km)")
                elif dist <= 2.5:
                    score += 20
                    reasons.append(f"Connecting Corridor ({round(dist, 1)}km)")
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
            # Proximity and cluster check across destination + all stops
            d_coord = ZONES.get(norm_dst)
            best_dist = 999.0
            best_place = ""
            dest_matched_cluster = False

            for place_name in [ride_dst, *stop_names]:
                for cluster_name, cluster_places in CAMPUS_CLUSTERS.items():
                    if norm_dst in cluster_places and place_name in cluster_places:
                        dest_matched_cluster = True
                        best_place = place_name
                        break
                p_coord = ZONES.get(place_name)
                if d_coord and p_coord:
                    d = _haversine_km(d_coord, p_coord)
                    if d < best_dist:
                        best_dist = d
                        best_place = place_name

            if dest_matched_cluster or best_dist <= 0.4:
                score += 48
                reasons.append(f"BRACU Campus Zone Drop-off ({best_place.title()})")
            elif best_dist <= 1.2:
                score += 35
                reasons.append(f"Near Drop-off ({round(best_dist, 1)}km of {best_place.title()})")
            elif best_dist <= 2.5:
                score += 20
                reasons.append(f"Nearby Corridor ({round(best_dist, 1)}km of {best_place.title()})")
            else:
                score += 0

        # Time & Class Schedule scoring
        if effective_time or scheduled_date:
            if r["scheduled_at"]:
                try:
                    r_dt = dt.fromisoformat(r["scheduled_at"].replace("Z", "+00:00"))
                    if effective_time:
                        # Extract hour:minute
                        req_parts = effective_time.split(":")
                        if len(req_parts) == 2:
                            req_h, req_m = int(req_parts[0]), int(req_parts[1])
                            diff_mins = abs((r_dt.hour * 60 + r_dt.minute) - (req_h * 60 + req_m))
                            if diff_mins <= 30:
                                score += 15
                                reasons.append(f"Class Time Match ({effective_time})")
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


def list_rides(user_id: str, female_only: bool=False):
    """List rides: mine (as driver/passenger) + open available rides."""
    conn = get_db()
    user = conn.execute("SELECT gender FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise DomainError(status_code=404, detail="User not found")

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


def get_ride(ride_id: str, user_id: str):
    """Ride detail including passenger stops and multi-stop progress."""
    conn = get_db()
    ride = conn.execute(
        """SELECT r.*, u.name AS driver_name, u.gender AS driver_gender FROM rides r
           JOIN users u ON r.driver_id = u.id WHERE r.id = ?""",
        (ride_id,)
    ).fetchone()
    if not ride:
        conn.close()
        raise DomainError(status_code=404, detail="Ride not found")
    if ride["driver_id"] != user_id:
        participant = conn.execute(
            "SELECT id FROM ride_passengers WHERE ride_id = ? AND passenger_id = ?",
            (ride_id, user_id)
        ).fetchone()
        if not participant:
            conn.close()
            raise DomainError(status_code=403, detail="Only ride participants can view this ride")

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


def ride_cost_split(ride_id: str, user_id: str):
    """Ride Cost Splitter — total = base_fare x surge; split by SEATS among accepted
    passengers, with whole-taka largest-remainder rounding so shares sum exactly
    to `total`.
    """
    conn = get_db()
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise DomainError(status_code=404, detail="Ride not found")

    is_driver = ride["driver_id"] == user_id
    participant = conn.execute(
        "SELECT id FROM ride_passengers WHERE ride_id = ? AND passenger_id = ? AND status IN ('accepted', 'completed')",
        (ride_id, user_id)
    ).fetchone()
    if not is_driver and not participant:
        conn.close()
        raise DomainError(status_code=403, detail="Only ride participants can view fare split details")

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


def get_ride_messages(ride_id: str, user_id: str):
    """Ride Chat history (participants only)."""
    conn = get_db()
    ride = conn.execute("SELECT driver_id FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise DomainError(status_code=404, detail="Ride not found")

    if ride["driver_id"] != user_id:
        participant = conn.execute(
            "SELECT id FROM ride_passengers WHERE ride_id = ? AND passenger_id = ? AND status IN ('accepted','completed')",
            (ride_id, user_id)
        ).fetchone()
        if not participant:
            conn.close()
            raise DomainError(status_code=403, detail="Only ride participants can view the chat")

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


# ---------------------------------------------------------------------------
# Feature 18: Ride Cancellation Policy & Penalty
#
# "Dispatch" is the moment the driver presses Start (status flips to 'active').
# Cancelling before dispatch is free. After dispatch the cancelling party is
# charged, because the other side has already committed: the driver is en route,
# or seats were held out of the pool.
#
# The fee is a percentage of what the ride was worth to the person cancelling,
# clamped so it is neither trivial on a cheap hop nor punitive on a long
# surge-priced trip. It is charged to the wallet (Feature 9) as a `penalty`
# ledger row, so it appears in the transaction history like any other movement.
# ---------------------------------------------------------------------------
PENALTY_RATE = 0.20      # 20% of the cancelling party's fare exposure
MIN_PENALTY = 20.0       # BDT floor, so a late cancel is never a rounding error
MAX_PENALTY = 150.0      # BDT ceiling


def _passenger_fare_share(conn, ride, passenger_id: str) -> float:
    """This passenger's seat-weighted slice of the ride total (Feature 5 math)."""
    for entry in ws.ride_shares(conn, ride):
        if entry["passenger_id"] == passenger_id:
            return entry["share"]
    return 0.0


def _cancellation_quote(conn, ride, user_id: str) -> dict:
    """What cancelling would cost `user_id` right now. No side effects.

    Shared by the preview endpoint and the cancel endpoint, so the warning the
    user sees and the amount actually charged can never drift apart.
    """
    is_driver = ride["driver_id"] == user_id
    role = "driver" if is_driver else "passenger"

    if is_driver:
        exposure = round(ride["base_fare"] * ride["surge_multiplier"], 2)
    else:
        exposure = _passenger_fare_share(conn, ride, user_id)

    if ride["status"] != "active":
        return {
            "will_be_charged": False,
            "penalty": 0.0,
            "exposure": exposure,
            "dispatched": False,
            "role": role,
            "reason": "This ride has not been dispatched yet, so cancelling is free.",
        }

    penalty = round(min(max(exposure * PENALTY_RATE, MIN_PENALTY), MAX_PENALTY), 2)
    who = "your passengers are already on board" if is_driver else "your driver is already en route"
    return {
        "will_be_charged": True,
        "penalty": penalty,
        "exposure": exposure,
        "dispatched": True,
        "role": role,
        "reason": (
            "This ride has already started and " + who + ". A BDT "
            + format(penalty, ".2f") + " late-cancellation fee ("
            + str(int(PENALTY_RATE * 100)) + "% of BDT " + format(exposure, ".2f")
            + ") will be charged to your wallet."
        ),
    }


def _load_cancellable(conn, ride_id: str, user_id: str):
    """Fetch the ride and confirm `user_id` is allowed to cancel it."""
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise DomainError(status_code=404, detail="Ride not found")
    if ride["status"] in ("completed", "cancelled"):
        status = ride["status"]
        conn.close()
        raise DomainError(
            status_code=400,
            detail="This ride is already " + status + " and cannot be cancelled",
        )

    is_driver = ride["driver_id"] == user_id
    seat = conn.execute(
        """SELECT * FROM ride_passengers
           WHERE ride_id = ? AND passenger_id = ? AND status IN ('requested', 'accepted')""",
        (ride_id, user_id),
    ).fetchone()
    if not is_driver and not seat:
        conn.close()
        raise DomainError(status_code=403, detail="You are not part of this ride")
    return ride, is_driver, seat


def cancellation_policy(ride_id: str, user_id: str):
    """Preview what cancelling costs, so the UI can warn before anything happens."""
    conn = get_db()
    ride, _is_driver, _seat = _load_cancellable(conn, ride_id, user_id)
    quote = _cancellation_quote(conn, ride, user_id)
    balance = ws.balance_of(conn, user_id)
    conn.close()
    return {
        "ride_id": ride_id,
        "ride_status": ride["status"],
        "wallet_balance": balance,
        "policy": {
            "free_before_dispatch": True,
            "penalty_rate": PENALTY_RATE,
            "min_penalty": MIN_PENALTY,
            "max_penalty": MAX_PENALTY,
        },
        **quote,
    }


def cancel_ride(ride_id: str, body: CancelRideRequest, user_id: str):
    """Driver cancels the whole ride; a passenger cancels only their own seat."""
    conn = get_db()
    ride, is_driver, seat = _load_cancellable(conn, ride_id, user_id)
    quote = _cancellation_quote(conn, ride, user_id)
    now = dt.utcnow().isoformat()
    reason = (body.reason or "").strip()[:300]

    charged = 0.0
    uncharged_note = ""
    if quote["will_be_charged"]:
        note = "Late cancellation - " + str(ride["source"]) + " to " + str(ride["destination"])
        try:
            with ws.atomic(conn):
                ws.post(conn, user_id, "penalty", -quote["penalty"],
                        ride_id=ride_id, note=note)
            charged = quote["penalty"]
        except ValueError as e:
            # Prepaid wallet with too little in it. The cancellation still goes
            # through -- trapping someone in a ride they cannot leave is worse --
            # but no money is invented: the fee goes uncollected and is reported.
            uncharged_note = str(e)

    if is_driver:
        conn.execute(
            """UPDATE rides SET status = 'cancelled', cancelled_at = ?, cancelled_by = ?,
                   cancel_reason = ? WHERE id = ?""",
            (now, user_id, reason, ride_id),
        )
        conn.execute(
            """UPDATE ride_passengers SET status = 'cancelled', cancelled_at = ?
               WHERE ride_id = ? AND status IN ('requested', 'accepted')""",
            (now, ride_id),
        )
        affected = "ride"
    else:
        conn.execute(
            """UPDATE ride_passengers SET status = 'cancelled', cancelled_at = ?,
                   penalty_amount = ? WHERE id = ?""",
            (now, charged, seat["id"]),
        )
        affected = "seat"

    conn.commit()
    balance = ws.balance_of(conn, user_id)
    conn.close()

    if charged > 0:
        msg = ("Cancelled. A BDT " + format(charged, ".2f")
               + " late-cancellation fee was charged to your wallet.")
    elif uncharged_note:
        msg = ("Cancelled. The BDT " + format(quote["penalty"], ".2f")
               + " late-cancellation fee could not be collected (" + uncharged_note + ").")
    else:
        msg = "Cancelled free of charge - the ride had not been dispatched yet."

    return {
        "message": msg,
        "cancelled": affected,
        "penalty_charged": charged,
        "penalty_due": quote["penalty"],
        "uncollected": bool(uncharged_note),
        "wallet_balance": balance,
        "ride_status": "cancelled" if is_driver else ride["status"],
    }

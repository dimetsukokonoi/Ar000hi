"""
Arooohi Backend — Ride History & Receipt Routes
Feature 10: Ride History & Receipt Log

History is a read-only projection over rides the user already took part in, as
driver or as passenger. Nothing new is stored: a "past trip" is any ride of theirs
in a terminal state (`completed` or `cancelled`).

The receipt reuses the Feature 5 splitter helper (`_split_total`) rather than
recomputing shares, so a receipt can never disagree with the live fare split shown
during the ride.
"""
from fastapi import APIRouter, HTTPException, Depends
from app.database import get_db
from app.auth import get_current_user_id
from app.routes.rides import _split_total

router = APIRouter()

TERMINAL_STATES = ("completed", "cancelled")


def _passenger_share(conn, ride, user_id: str):
    """What this passenger owed for the ride: their seats' slice of the total.
    Returns (share, seats, total_seats) or (None, 0, ...) if they were not on board."""
    accepted = conn.execute(
        """SELECT passenger_id, seats FROM ride_passengers
           WHERE ride_id = ? AND status IN ('accepted', 'completed')
           ORDER BY created_at ASC""",
        (ride["id"],)
    ).fetchall()

    weights = [max(int(r["seats"]), 1) for r in accepted]
    total_seats = sum(weights)
    if total_seats == 0:
        return None, 0, 0

    total = round(ride["base_fare"] * ride["surge_multiplier"], 2)
    shares = _split_total(total, total_seats)

    idx = 0
    for r, w in zip(accepted, weights):
        if r["passenger_id"] == user_id:
            return round(sum(shares[idx:idx + w]), 2), w, total_seats
        idx += w
    return None, 0, total_seats


def _penalty_for(conn, user_id: str, ride_id: str) -> float:
    """Total cancellation penalty this user paid on this ride (positive number)."""
    row = conn.execute(
        """SELECT COALESCE(SUM(-amount), 0) AS p FROM wallet_transactions
           WHERE user_id = ? AND ride_id = ? AND kind = 'penalty'""",
        (user_id, ride_id)
    ).fetchone()
    return round(row["p"], 2)


@router.get("")
def ride_history(role: str = "all", user_id: str = Depends(get_current_user_id)):
    """Past trips (newest first). `role` filters to 'driver' | 'passenger' | 'all'."""
    if role not in ("all", "driver", "passenger"):
        raise HTTPException(status_code=400, detail="role must be all, driver, or passenger")

    conn = get_db()
    placeholders = ",".join("?" * len(TERMINAL_STATES))
    # A ride is "past" for this user when EITHER the ride itself reached a terminal
    # state (they drove it, or rode it to the end), OR their own seat is cancelled.
    # The second arm matters because a passenger dropping out of a still-running
    # ride leaves `rides.status = 'active'` — without it, a trip they cancelled and
    # were charged a penalty for would never appear in their history.
    rides = conn.execute(
        f"""SELECT r.*, u.name AS driver_name
            FROM rides r JOIN users u ON r.driver_id = u.id
            WHERE (r.status IN ({placeholders})
                   AND (r.driver_id = ?
                        OR r.id IN (SELECT ride_id FROM ride_passengers
                                    WHERE passenger_id = ? AND status != 'requested')))
               OR r.id IN (SELECT ride_id FROM ride_passengers
                           WHERE passenger_id = ? AND status = 'cancelled')
            ORDER BY COALESCE(r.ended_at, r.cancelled_at, r.created_at) DESC""",
        (*TERMINAL_STATES, user_id, user_id, user_id)
    ).fetchall()

    trips = []
    for r in rides:
        as_driver = r["driver_id"] == user_id
        seat_row = conn.execute(
            """SELECT seats, status, penalty_amount FROM ride_passengers
               WHERE ride_id = ? AND passenger_id = ?""",
            (r["id"], user_id)
        ).fetchone()

        # Report the outcome from THIS user's point of view: a passenger who
        # cancelled sees "cancelled" even if the ride itself ran to completion.
        if not as_driver and seat_row and seat_row["status"] == "cancelled":
            outcome = "cancelled"
        else:
            outcome = r["status"]

        total = round(r["base_fare"] * r["surge_multiplier"], 2)
        if as_driver:
            amount = total
        elif outcome == "cancelled":
            amount = 0.0   # a cancelled seat owes no fare, only the penalty below
        else:
            amount, _seats, _total_seats = _passenger_share(conn, r, user_id)

        trips.append({
            "ride_id": r["id"],
            "role": "driver" if as_driver else "passenger",
            "source": r["source"],
            "destination": r["destination"],
            "status": outcome,
            "driver_name": r["driver_name"],
            "distance_km": r["distance_km"],
            "base_fare": r["base_fare"],
            "surge_multiplier": r["surge_multiplier"],
            "ride_total": total,
            "amount": amount,
            "seats": seat_row["seats"] if seat_row else None,
            "penalty_paid": _penalty_for(conn, user_id, r["id"]),
            "scheduled_at": r["scheduled_at"],
            "started_at": r["started_at"],
            "ended_at": r["ended_at"],
            "cancelled_at": r["cancelled_at"],
            "created_at": r["created_at"],
        })

    conn.close()

    if role != "all":
        trips = [t for t in trips if t["role"] == role]

    completed = [t for t in trips if t["status"] == "completed"]
    return {
        "trips": trips,
        "summary": {
            "total_trips": len(trips),
            "completed": len(completed),
            "cancelled": len(trips) - len(completed),
            "as_driver": sum(1 for t in trips if t["role"] == "driver"),
            "as_passenger": sum(1 for t in trips if t["role"] == "passenger"),
            "total_km": round(sum(t["distance_km"] or 0 for t in completed), 2),
            "total_spent": round(
                sum(t["amount"] or 0 for t in completed if t["role"] == "passenger"), 2
            ),
            "total_penalties": round(sum(t["penalty_paid"] for t in trips), 2),
        },
    }


@router.get("/{ride_id}/receipt")
def ride_receipt(ride_id: str, user_id: str = Depends(get_current_user_id)):
    """Printable receipt for one past trip. Participants only."""
    conn = get_db()
    ride = conn.execute(
        """SELECT r.*, u.name AS driver_name, u.bracu_email AS driver_email
           FROM rides r JOIN users u ON r.driver_id = u.id WHERE r.id = ?""",
        (ride_id,)
    ).fetchone()
    if not ride:
        conn.close()
        raise HTTPException(status_code=404, detail="Ride not found")

    as_driver = ride["driver_id"] == user_id
    seat_row = conn.execute(
        """SELECT seats, status FROM ride_passengers
           WHERE ride_id = ? AND passenger_id = ? AND status != 'requested'""",
        (ride_id, user_id)
    ).fetchone()
    if not as_driver and not seat_row:
        conn.close()
        raise HTTPException(status_code=403, detail="Only ride participants can view this receipt")

    # A cancelled seat is terminal for THIS user even while the ride runs on —
    # they may have been charged a penalty and are entitled to the receipt for it.
    seat_cancelled = bool(seat_row) and seat_row["status"] == "cancelled"
    if ride["status"] not in TERMINAL_STATES and not seat_cancelled:
        conn.close()
        raise HTTPException(
            status_code=400, detail="A receipt is only available once the ride has ended"
        )

    me = conn.execute("SELECT name, bracu_email FROM users WHERE id = ?", (user_id,)).fetchone()

    lines = []
    total = round(ride["base_fare"] * ride["surge_multiplier"], 2)
    if as_driver:
        amount = total
        lines.append({"label": "Ride total collected", "amount": total})
    elif seat_cancelled:
        amount = 0.0
        lines.append({"label": "Cancelled booking — no fare charged", "amount": 0.0})
    else:
        share, seats, total_seats = _passenger_share(conn, ride, user_id)
        amount = share or 0.0
        base_label = "Base fare (BDT {:.2f})".format(ride["base_fare"])
        lines.append({"label": base_label, "amount": ride["base_fare"]})
        if ride["surge_multiplier"] > 1:
            lines.append({
                "label": "Peak-hour surge x{}".format(ride["surge_multiplier"]),
                "amount": round(total - ride["base_fare"], 2),
            })
        lines.append({
            "label": "Your share ({} of {} seats)".format(seats, total_seats),
            "amount": amount,
        })

    penalty = _penalty_for(conn, user_id, ride_id)
    if penalty:
        lines.append({"label": "Late cancellation penalty", "amount": penalty})

    conn.close()

    return {
        "receipt_no": "ARH-{}".format(ride_id[:8].upper()),
        "issued_to": {"name": me["name"], "email": me["bracu_email"]},
        "role": "driver" if as_driver else "passenger",
        "ride": {
            "ride_id": ride_id,
            "source": ride["source"],
            "destination": ride["destination"],
            "status": ride["status"],
            "driver_name": ride["driver_name"],
            "distance_km": ride["distance_km"],
            "base_fare": ride["base_fare"],
            "surge_multiplier": ride["surge_multiplier"],
            "ride_total": total,
            "started_at": ride["started_at"],
            "ended_at": ride["ended_at"],
            "cancelled_at": ride["cancelled_at"],
        },
        "lines": lines,
        "amount_due": round(amount + penalty, 2),
        "currency": "BDT",
    }

"""History model: business rules and persistence, independent of FastAPI."""
from datetime import datetime as dt
from zoneinfo import ZoneInfo
from app.models import ledger as ws
from app.models.database import get_db
from app.models.errors import DomainError

BD_TZ = ZoneInfo("Asia/Dhaka")
RECEIPT_PREFIX = "ARH"


def _ledger_for(conn, ride_id: str, user_id: str):
    """The wallet row this ride produced for this user, if it settled."""
    return conn.execute(
        """SELECT id, kind, amount, platform_fee, created_at
           FROM transactions
           WHERE ride_id = ? AND user_id = ? AND kind IN ('ride_debit', 'ride_credit')
           LIMIT 1""",
        (ride_id, user_id),
    ).fetchone()


def _receipt_no(ride_id: str, ended_at: str | None) -> str:
    """Stable, human-quotable receipt number. Same ride always yields the same one."""
    stamp = (ended_at or "")[:10].replace("-", "") or "00000000"
    return f"{RECEIPT_PREFIX}-{stamp}-{ride_id[:6].upper()}"


def _when(ride) -> str | None:
    return ride["ended_at"] or ride["scheduled_at"] or ride["created_at"]


def list_history(user_id: str, role: str='all', status: str='completed', limit: int=50):
    """Past trips, newest first, across both roles."""
    conn = get_db()
    status_sql = "" if status == "all" else " AND r.status = 'completed'"
    trips = []

    if role in ("all", "driver"):
        rows = conn.execute(
            f"""SELECT r.*, (SELECT COUNT(*) FROM ride_passengers rp
                             WHERE rp.ride_id = r.id
                               AND rp.status IN ('accepted','completed')) AS pax
                FROM rides r
                WHERE r.driver_id = ?{status_sql}""",
            (user_id,),
        ).fetchall()
        for r in rows:
            led = _ledger_for(conn, r["id"], user_id)
            trips.append({
                "ride_id": r["id"],
                "role": "driver",
                "source": r["source"],
                "destination": r["destination"],
                "status": r["status"],
                "when": _when(r),
                "distance_km": r["distance_km"],
                "passengers": r["pax"],
                "counterparty": f"{r['pax']} passenger" + ("" if r["pax"] == 1 else "s"),
                "amount": round(led["amount"], 2) if led else 0.0,
                "settled": led is not None,
                "female_only": bool(r["female_only"]),
                "receipt_no": _receipt_no(r["id"], _when(r)),
            })

    if role in ("all", "passenger"):
        rows = conn.execute(
            f"""SELECT r.*, rp.seats, rp.pickup_stop, rp.dropoff_stop,
                       rp.status AS my_status, u.name AS driver_name
                FROM ride_passengers rp
                JOIN rides r ON r.id = rp.ride_id
                JOIN users u ON u.id = r.driver_id
                WHERE rp.passenger_id = ?
                  AND rp.status IN ('accepted','completed'){status_sql}""",
            (user_id,),
        ).fetchall()
        for r in rows:
            led = _ledger_for(conn, r["id"], user_id)
            if led:
                amount = round(abs(led["amount"]), 2)
            else:
                shares = ws.ride_shares(conn, r)
                mine = next((s for s in shares if s["passenger_id"] == user_id), None)
                amount = mine["share"] if mine else 0.0
            trips.append({
                "ride_id": r["id"],
                "role": "passenger",
                "source": r["pickup_stop"] or r["source"],
                "destination": r["dropoff_stop"] or r["destination"],
                "status": r["status"],
                "when": _when(r),
                "distance_km": r["distance_km"],
                "passengers": r["seats"],
                "counterparty": r["driver_name"],
                "amount": amount,
                "settled": led is not None,
                "female_only": bool(r["female_only"]),
                "receipt_no": _receipt_no(r["id"], _when(r)),
            })

    conn.close()
    trips.sort(key=lambda t: t["when"] or "", reverse=True)
    return trips[:limit]


def history_summary(user_id: str):
    """Lifetime totals across both roles — spent as a rider, earned as a driver."""
    conn = get_db()
    spent = conn.execute(
        """SELECT COALESCE(SUM(ABS(amount)), 0) AS s, COUNT(*) AS n
           FROM transactions WHERE user_id = ? AND kind = 'ride_debit'""",
        (user_id,),
    ).fetchone()
    earned = conn.execute(
        """SELECT COALESCE(SUM(amount), 0) AS s, COUNT(*) AS n
           FROM transactions WHERE user_id = ? AND kind = 'ride_credit'""",
        (user_id,),
    ).fetchone()
    as_driver = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(distance_km), 0) AS km FROM rides WHERE driver_id = ? AND status = 'completed'",
        (user_id,),
    ).fetchone()
    as_passenger = conn.execute(
        """SELECT COUNT(*) AS n, COALESCE(SUM(r.distance_km), 0) AS km
           FROM ride_passengers rp JOIN rides r ON r.id = rp.ride_id
           WHERE rp.passenger_id = ? AND r.status = 'completed'
             AND rp.status IN ('accepted','completed')""",
        (user_id,),
    ).fetchone()
    conn.close()

    return {
        "trips_as_driver": as_driver["n"],
        "trips_as_passenger": as_passenger["n"],
        "total_trips": as_driver["n"] + as_passenger["n"],
        "total_spent": round(spent["s"], 2),
        "total_earned": round(earned["s"], 2),
        "net": round(earned["s"] - spent["s"], 2),
        "distance_km": round(as_driver["km"] + as_passenger["km"], 2),
    }


def get_receipt(ride_id: str, user_id: str):
    """Full receipt for one ride. Participants only."""
    conn = get_db()
    ride = conn.execute("SELECT * FROM rides WHERE id = ?", (ride_id,)).fetchone()
    if not ride:
        conn.close()
        raise DomainError(status_code=404, detail="Ride not found")

    # A receipt documents a COMPLETED trip. Serving one for a scheduled or active
    # ride produces a document that looks like proof of payment for a trip that
    # has not happened.
    if ride["status"] != "completed":
        conn.close()
        raise DomainError(
            status_code=400,
            detail=(f"This ride is {ride['status']}, not completed. "
                    "A receipt is issued once the trip finishes."),
        )

    is_driver = ride["driver_id"] == user_id
    mine = conn.execute(
        """SELECT * FROM ride_passengers
           WHERE ride_id = ? AND passenger_id = ? AND status IN ('accepted','completed')""",
        (ride_id, user_id),
    ).fetchone()
    if not is_driver and not mine:
        conn.close()
        raise DomainError(status_code=403, detail="Only ride participants can view this receipt")

    driver = conn.execute("SELECT name, bracu_email FROM users WHERE id = ?", (ride["driver_id"],)).fetchone()
    stops = conn.execute(
        "SELECT sequence, place, status FROM ride_stops WHERE ride_id = ? ORDER BY sequence ASC",
        (ride_id,),
    ).fetchall()

    # Same numbers the cost splitter shows — one shared implementation.
    shares = ws.ride_shares(conn, ride)
    total = round(ride["base_fare"] * ride["surge_multiplier"], 2)
    led = _ledger_for(conn, ride_id, user_id)
    conn.close()

    if is_driver:
        your_amount = round(led["amount"], 2) if led else 0.0
        expected = round(sum(s["share"] for s in shares), 2)
        line = "Fare received from passengers"
    else:
        mine_share = next((s for s in shares if s["passenger_id"] == user_id), None)
        expected = mine_share["share"] if mine_share else 0.0
        your_amount = round(abs(led["amount"]), 2) if led else 0.0
        line = "Your share of the fare"

    # `paid` alone is not enough: a driver can be credited for SOME passengers and
    # not others, which is neither fully paid nor fully unpaid.
    shortfall = round(max(expected - your_amount, 0.0), 2) if led else 0.0
    fully_paid = led is not None and shortfall <= 0.005

    return {
        "receipt_no": _receipt_no(ride_id, _when(ride)),
        "issued_at": dt.now(BD_TZ).isoformat(),
        "ride_id": ride_id,
        "role": "driver" if is_driver else "passenger",
        "status": ride["status"],
        "paid": led is not None,
        "fully_paid": fully_paid,
        "shortfall": shortfall,
        "payment_method": ("Arooohi Wallet (bKash)" if fully_paid
                           else "Arooohi Wallet (bKash) — partially settled" if led
                           else "Unsettled"),
        "transaction_id": led["id"] if led else None,
        "paid_at": led["created_at"] if led else None,
        "driver_name": driver["name"] if driver else "Unknown",
        "route": {
            "source": ride["source"],
            "destination": ride["destination"],
            "pickup_stop": (mine["pickup_stop"] if mine else None) or ride["source"],
            "dropoff_stop": (mine["dropoff_stop"] if mine else None) or ride["destination"],
            "stops": [{"sequence": s["sequence"], "place": s["place"], "status": s["status"]} for s in stops],
        },
        "when": _when(ride),
        "started_at": ride["started_at"],
        "ended_at": ride["ended_at"],
        "distance_km": ride["distance_km"],
        "female_only": bool(ride["female_only"]),
        "fare": {
            "base_fare": round(ride["base_fare"], 2),
            "surge_multiplier": ride["surge_multiplier"],
            "total": total,
            "seats": (mine["seats"] if mine else None),
            "platform_fee": round(led["platform_fee"], 2) if led else 0.0,
        },
        "your_line_label": line,
        "your_amount": your_amount,
        "expected_amount": expected,
        "breakdown": shares,
    }

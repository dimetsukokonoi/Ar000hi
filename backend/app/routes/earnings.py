"""
Arooohi Backend — Driver Earnings Routes
Feature 16: Driver Earnings Dashboard

No new ride data is needed: `end_ride()` already stamps `status='completed'` and
`ended_at`, and every ride stores `base_fare` + `surge_multiplier`. Gross earnings
for a ride are therefore `base_fare * surge_multiplier` — the same figure the cost
splitter (Feature 5) divides among passengers, so the driver's dashboard and the
passengers' receipts can never disagree.

Payouts: completed-but-unpaid rides accumulate as "pending". `POST /payout` sweeps
them into the wallet (Feature 9) as a single `payout` credit, and each swept ride
is marked by a ledger row carrying its `ride_id`, which is what makes a ride "paid".
"""
from datetime import datetime as dt, timedelta
from fastapi import APIRouter, HTTPException, Depends
from app.database import get_db
from app.auth import get_current_user_id
from app.routes.wallet import post_transaction

router = APIRouter()

PLATFORM_FEE_RATE = 0.10   # Arooohi keeps 10% of gross; the driver nets the rest.
WEEKS_SHOWN = 6


def _gross(ride) -> float:
    return round(ride["base_fare"] * ride["surge_multiplier"], 2)


def _net(gross: float) -> float:
    return round(gross * (1 - PLATFORM_FEE_RATE), 2)


def _week_start(iso_ts: str) -> str:
    """Monday of the week containing `iso_ts`, as YYYY-MM-DD."""
    try:
        d = dt.fromisoformat(iso_ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return "unknown"
    return (d - timedelta(days=d.weekday())).date().isoformat()


def _completed_rides(conn, driver_id: str):
    return conn.execute(
        """SELECT r.id, r.source, r.destination, r.base_fare, r.surge_multiplier,
                  r.distance_km, r.ended_at, r.created_at,
                  (SELECT COUNT(*) FROM ride_passengers rp
                   WHERE rp.ride_id = r.id AND rp.status IN ('accepted', 'completed')) AS passenger_count,
                  (SELECT COUNT(*) FROM wallet_transactions wt
                   WHERE wt.ride_id = r.id AND wt.user_id = r.driver_id
                     AND wt.kind = 'payout') AS paid_out
           FROM rides r
           WHERE r.driver_id = ? AND r.status = 'completed'
           ORDER BY COALESCE(r.ended_at, r.created_at) DESC""",
        (driver_id,)
    ).fetchall()


@router.get("/summary")
def earnings_summary(user_id: str = Depends(get_current_user_id)):
    """Lifetime + weekly earnings, ride count, and the pending payout balance."""
    conn = get_db()
    rides = _completed_rides(conn, user_id)
    conn.close()

    total_gross = 0.0
    total_net = 0.0
    pending = 0.0
    total_km = 0.0
    total_passengers = 0
    weekly = {}
    breakdown = []

    for r in rides:
        gross = _gross(r)
        net = _net(gross)
        stamp = r["ended_at"] or r["created_at"]
        wk = _week_start(stamp)

        total_gross += gross
        total_net += net
        total_km += r["distance_km"] or 0.0
        total_passengers += r["passenger_count"]
        if not r["paid_out"]:
            pending += net

        bucket = weekly.setdefault(wk, {"week_start": wk, "rides": 0, "gross": 0.0, "net": 0.0})
        bucket["rides"] += 1
        bucket["gross"] = round(bucket["gross"] + gross, 2)
        bucket["net"] = round(bucket["net"] + net, 2)

        breakdown.append({
            "ride_id": r["id"],
            "source": r["source"],
            "destination": r["destination"],
            "base_fare": r["base_fare"],
            "surge_multiplier": r["surge_multiplier"],
            "gross": gross,
            "net": net,
            "passengers": r["passenger_count"],
            "distance_km": r["distance_km"],
            "ended_at": r["ended_at"],
            "paid_out": bool(r["paid_out"]),
            "week_start": wk,
        })

    weeks = sorted(weekly.values(), key=lambda w: w["week_start"], reverse=True)[:WEEKS_SHOWN]
    this_week = _week_start(dt.utcnow().isoformat())
    current = next((w for w in weeks if w["week_start"] == this_week), None)
    best = max(weeks, key=lambda w: w["net"], default=None)

    return {
        "rides_completed": len(rides),
        "total_gross": round(total_gross, 2),
        "total_net": round(total_net, 2),
        "platform_fee_rate": PLATFORM_FEE_RATE,
        "platform_fee_total": round(total_gross - total_net, 2),
        "pending_payout": round(pending, 2),
        "total_km": round(total_km, 2),
        "passengers_served": total_passengers,
        "avg_per_ride": round(total_net / len(rides), 2) if rides else 0.0,
        "this_week": current or {"week_start": this_week, "rides": 0, "gross": 0.0, "net": 0.0},
        "best_week": best,
        "weekly": weeks,
        "rides": breakdown,
    }


@router.post("/payout")
def request_payout(user_id: str = Depends(get_current_user_id)):
    """Sweep every unpaid completed ride into the wallet as one payout credit."""
    conn = get_db()
    rides = _completed_rides(conn, user_id)
    unpaid = [r for r in rides if not r["paid_out"]]

    if not unpaid:
        conn.close()
        raise HTTPException(status_code=400, detail="No earnings are pending payout right now")

    total = round(sum(_net(_gross(r)) for r in unpaid), 2)

    # One ledger row per ride keeps each ride individually traceable as paid,
    # which is what `paid_out` reads back on the next summary call.
    tx = None
    for r in unpaid:
        tx = post_transaction(
            conn, user_id, "payout", _net(_gross(r)),
            ride_id=r["id"],
            note=f"Payout for ride {r['source']} to {r['destination']}",
        )
    conn.commit()
    conn.close()

    return {
        "message": f"BDT {total:.2f} paid out to your wallet",
        "rides_paid": len(unpaid),
        "amount": total,
        "balance": tx["balance_after"] if tx else None,
    }

"""
Arooohi Backend — Driver Earnings Routes
Feature 16: Driver Earnings Dashboard

Source of truth is the wallet LEDGER, not a re-computation over `rides`: a driver
earned exactly what was credited to them (`transactions.kind = 'ride_credit'`).
Deriving it a second time from `base_fare x surge` would let the dashboard and the
wallet disagree, which is the classic way a payments UI loses trust.

Rides that completed but were never settled (they finished before the wallet
existed, or a passenger could not pay) are reported SEPARATELY as `unsettled`
rather than being silently folded into earnings or silently dropped.

Weeks are bucketed in Asia/Dhaka, matching the surge schedule, so "this week"
means what a Dhaka student thinks it means.
"""
from datetime import datetime as dt, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query

from app import wallet_service as ws
from app.auth import get_current_user_id
from app.database import get_db

router = APIRouter()

BD_TZ = ZoneInfo("Asia/Dhaka")


def _parse_utc(value: str) -> dt | None:
    """Ledger rows use SQLite's 'YYYY-MM-DD HH:MM:SS'; ride timestamps use
    isoformat(). Accept both and return an aware UTC datetime."""
    if not value:
        return None
    text = value.strip().replace("T", " ")
    if text.endswith("Z"):
        text = text[:-1]
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.strptime(text, fmt).replace(tzinfo=ZoneInfo("UTC"))
        except ValueError:
            continue
    return None


def _to_bd(value: str) -> dt | None:
    utc = _parse_utc(value)
    return utc.astimezone(BD_TZ) if utc else None


def _week_start(d: dt) -> dt:
    """Monday 00:00 in Dhaka local time."""
    start = d - timedelta(days=d.weekday())
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def _credits(conn, user_id: str):
    return conn.execute(
        """SELECT t.id, t.amount, t.platform_fee, t.created_at, t.ride_id,
                  r.source, r.destination, r.distance_km, r.base_fare,
                  r.surge_multiplier, r.ended_at
           FROM transactions t
           LEFT JOIN rides r ON r.id = t.ride_id
           WHERE t.user_id = ? AND t.kind = 'ride_credit'
           ORDER BY t.created_at DESC""",
        (user_id,),
    ).fetchall()


def _uncollected(conn, user_id: str) -> list[dict]:
    """Completed rides where the driver did NOT receive the full fare.

    Covers two cases, and the second one is easy to miss: a ride can settle
    *partially* when some passengers pay and others cannot. An earlier version
    tested `NOT EXISTS (... ride_credit)`, which is all-or-nothing — a half-paid
    ride has a credit row, so its shortfall disappeared from the totals entirely
    and the driver was never told they were short.

    Compares what the passengers owed (the splitter's numbers) against what was
    actually credited, and reports the difference.
    """
    rides = conn.execute(
        """SELECT * FROM rides
           WHERE driver_id = ? AND status = 'completed'
           ORDER BY ended_at DESC""",
        (user_id,),
    ).fetchall()

    out = []
    for r in rides:
        shares = ws.ride_shares(conn, r)
        expected = round(sum(s["share"] for s in shares), 2)
        if expected <= 0:
            continue   # nobody aboard: nothing was ever owed
        led = conn.execute(
            """SELECT amount, platform_fee FROM transactions
               WHERE ride_id = ? AND user_id = ? AND kind = 'ride_credit'""",
            (r["id"], user_id),
        ).fetchone()
        # Compare gross-of-fee, so a platform commission is not mistaken for a shortfall.
        received = round(led["amount"] + led["platform_fee"], 2) if led else 0.0
        shortfall = round(expected - received, 2)
        if shortfall <= 0.005:
            continue
        out.append({
            "ride_id": r["id"],
            "source": r["source"],
            "destination": r["destination"],
            "distance_km": r["distance_km"],
            "ended_at": r["ended_at"],
            "passengers": len(shares),
            "expected": expected,
            "received": received,
            "shortfall": shortfall,
            "kind": "unpaid" if received <= 0.005 else "partial",
        })
    return out


def _passenger_count(conn, ride_id: str) -> int:
    if not ride_id:
        return 0
    return conn.execute(
        """SELECT COUNT(*) AS c FROM ride_passengers
           WHERE ride_id = ? AND status IN ('accepted','completed')""",
        (ride_id,),
    ).fetchone()["c"]


@router.get("/summary")
def earnings_summary(user_id: str = Depends(get_current_user_id)):
    """Headline figures: lifetime net, ride count, this week vs last, payout ready."""
    conn = get_db()
    ws.get_or_create_wallet(conn, user_id)
    conn.commit()

    credits = _credits(conn, user_id)
    pending = _uncollected(conn, user_id)
    balance = ws.balance_of(conn, user_id)

    total_net = round(sum(c["amount"] for c in credits), 2)
    total_fees = round(sum(c["platform_fee"] for c in credits), 2)
    rides_paid = len(credits)

    now_bd = dt.now(BD_TZ)
    this_start = _week_start(now_bd)
    last_start = this_start - timedelta(days=7)

    this_week = last_week = 0.0
    this_week_rides = 0
    total_km = 0.0
    total_passengers = 0
    for c in credits:
        when = _to_bd(c["created_at"])
        if when:
            if when >= this_start:
                this_week = round(this_week + c["amount"], 2)
                this_week_rides += 1
            elif when >= last_start:
                last_week = round(last_week + c["amount"], 2)
        total_km += c["distance_km"] or 0.0
        total_passengers += _passenger_count(conn, c["ride_id"])

    # Lost income = the fare that was owed but never received, including the
    # shortfall on rides that only settled partially.
    unsettled_value = round(sum(p["shortfall"] for p in pending), 2)
    unsettled_rides = len(pending)
    fully_unpaid = sum(1 for p in pending if p["kind"] == "unpaid")
    partially_paid = sum(1 for p in pending if p["kind"] == "partial")
    conn.close()

    if last_week > 0:
        change_pct = round((this_week - last_week) / last_week * 100, 1)
    else:
        change_pct = 100.0 if this_week > 0 else 0.0

    return {
        "total_earned": total_net,
        "total_platform_fees": total_fees,
        "gross_earned": round(total_net + total_fees, 2),
        "rides_paid": rides_paid,
        "avg_per_ride": round(total_net / rides_paid, 2) if rides_paid else 0.0,
        "this_week": this_week,
        "this_week_rides": this_week_rides,
        "last_week": last_week,
        "change_pct": change_pct,
        "available_payout": balance,
        "total_distance_km": round(total_km, 2),
        "total_passengers": total_passengers,
        "unsettled_rides": unsettled_rides,
        "unsettled_value": unsettled_value,
        "fully_unpaid_rides": fully_unpaid,
        "partially_paid_rides": partially_paid,
        "week_starting": this_start.date().isoformat(),
    }


def _bucket_series(credits, count: int, step_days: int, label_fmt: str) -> list[dict]:
    """Bucket ride credits into `count` consecutive periods ending with the
    current one, in Dhaka time, oldest first.

    Shared by /weekly (step 7) and /daily (step 1) so the two views can never
    drift apart. Empty periods are KEPT: dropping a zero bucket would compress
    the time axis and make an idle stretch look like continuous activity.
    """
    now_bd = dt.now(BD_TZ)
    anchor = _week_start(now_bd) if step_days == 7 else now_bd.replace(
        hour=0, minute=0, second=0, microsecond=0)

    def bucket_start(when: dt) -> dt:
        if step_days == 7:
            return _week_start(when)
        return when.replace(hour=0, minute=0, second=0, microsecond=0)

    buckets: dict[str, dict] = {}
    for i in range(count - 1, -1, -1):
        start = anchor - timedelta(days=step_days * i)
        buckets[start.date().isoformat()] = {
            "period_start": start.date().isoformat(),
            "label": start.strftime(label_fmt),
            "amount": 0.0,
            "rides": 0,
            "is_current": i == 0,
        }

    earliest = anchor - timedelta(days=step_days * (count - 1))
    for c in credits:
        when = _to_bd(c["created_at"])
        if not when or when < earliest:
            continue
        key = bucket_start(when).date().isoformat()
        if key in buckets:
            buckets[key]["amount"] = round(buckets[key]["amount"] + c["amount"], 2)
            buckets[key]["rides"] += 1

    return list(buckets.values())


@router.get("/weekly")
def earnings_weekly(weeks: int = Query(8, ge=1, le=26),
                    user_id: str = Depends(get_current_user_id)):
    """Earnings per week (Monday start, Dhaka time), oldest first."""
    conn = get_db()
    credits = _credits(conn, user_id)
    conn.close()

    series = _bucket_series(credits, weeks, 7, "%d %b")
    amounts = [b["amount"] for b in series]
    return {
        # `weeks` kept for backwards compatibility; `buckets` is the shared key.
        "weeks": series,
        "buckets": series,
        "period": "week",
        "max": max(amounts) if amounts else 0.0,
        "total": round(sum(amounts), 2),
        "timezone": "Asia/Dhaka",
    }


@router.get("/daily")
def earnings_daily(days: int = Query(14, ge=1, le=90),
                   user_id: str = Depends(get_current_user_id)):
    """Earnings per calendar day (Dhaka time), oldest first.

    Expect this view to look sparse: a student driver runs a handful of rides a
    week, so most days are legitimately zero.
    """
    conn = get_db()
    credits = _credits(conn, user_id)
    conn.close()

    series = _bucket_series(credits, days, 1, "%d %b")
    amounts = [b["amount"] for b in series]
    return {
        "days": series,
        "buckets": series,
        "period": "day",
        "max": max(amounts) if amounts else 0.0,
        "total": round(sum(amounts), 2),
        "timezone": "Asia/Dhaka",
    }


@router.get("/rides")
def earnings_rides(limit: int = Query(20, ge=1, le=100),
                   user_id: str = Depends(get_current_user_id)):
    """Per-ride earnings, newest first, with unsettled rides flagged."""
    conn = get_db()
    credits = _credits(conn, user_id)
    pending = _uncollected(conn, user_id)
    short_by_ride = {p["ride_id"]: p for p in pending}

    rows = []
    for c in credits:
        short = short_by_ride.get(c["ride_id"])
        rows.append({
            "ride_id": c["ride_id"],
            "source": c["source"] or "—",
            "destination": c["destination"] or "—",
            "when": c["created_at"],
            "distance_km": c["distance_km"],
            "passengers": _passenger_count(conn, c["ride_id"]),
            "gross": round(c["amount"] + c["platform_fee"], 2),
            "platform_fee": round(c["platform_fee"], 2),
            "net": round(c["amount"], 2),
            "settled": True,
            # A credited ride can still be short if only some passengers paid.
            "shortfall": short["shortfall"] if short else 0.0,
            "expected": short["expected"] if short else round(c["amount"] + c["platform_fee"], 2),
        })

    for p in pending:
        if p["kind"] != "unpaid":
            continue   # partials are already represented by their credit row above
        rows.append({
            "ride_id": p["ride_id"],
            "source": p["source"],
            "destination": p["destination"],
            "when": p["ended_at"],
            "distance_km": p["distance_km"],
            "passengers": p["passengers"],
            "gross": p["expected"],
            "platform_fee": 0.0,
            "net": 0.0,
            "settled": False,
            "shortfall": p["shortfall"],
            "expected": p["expected"],
        })
    conn.close()

    rows.sort(key=lambda r: r["when"] or "", reverse=True)
    return rows[:limit]

"""
Arooohi Backend — Wallet Ledger Service
Feature 9: Wallet & bKash Integration

Money rules enforced here (and nowhere else):

1. The `transactions` table is APPEND-ONLY. A correction is a new opposing row,
   never an UPDATE or DELETE. `wallets.balance` is a cached mirror of
   SUM(transactions.amount) and is verified by GET /api/wallet/reconcile.
2. `amount` is signed from the wallet owner's point of view: credit > 0, debit < 0.
3. Every multi-row money movement runs inside `atomic()` (BEGIN IMMEDIATE), so a
   rider debit and the matching driver credit can never land one without the other.
4. Ride settlement is idempotent: the unique index
   uq_transactions_ride_leg(ride_id, user_id, kind) makes a second settlement of
   the same ride a no-op rather than a double charge.
"""
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime as dt

# Platform cut of each ride fare. 0% by default — the column exists so switching
# this on later is a config change, not a migration + backfill.
PLATFORM_COMMISSION_RATE = float(os.getenv("PLATFORM_COMMISSION_RATE", "0.0"))

MIN_TOPUP = 10.0
MAX_TOPUP = 25000.0


@contextmanager
def atomic(conn: sqlite3.Connection):
    """Run a block as one all-or-nothing SQLite transaction."""
    prev = conn.isolation_level
    conn.isolation_level = None          # take manual control
    conn.execute("BEGIN IMMEDIATE")      # reserve the write lock up front
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.isolation_level = prev


def split_total(total: float, parts: int) -> list[float]:
    """Largest-remainder split at paisa resolution so the parts sum EXACTLY to
    `total` (naive round(total/n, 2) drifts). Shared with the cost splitter."""
    if parts <= 0:
        return []
    total_paisa = round(total * 100)
    base = total_paisa // parts
    remainder = total_paisa - base * parts
    shares = [round(base / 100.0, 2)] * parts
    for i in range(remainder):
        shares[i] = round((base + 1) / 100.0, 2)
    return shares


def get_or_create_wallet(conn: sqlite3.Connection, user_id: str) -> sqlite3.Row:
    """Wallets are created lazily on first access."""
    row = conn.execute("SELECT * FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        return row
    conn.execute(
        "INSERT OR IGNORE INTO wallets (id, user_id, balance) VALUES (?, ?, 0.0)",
        (str(uuid.uuid4()), user_id),
    )
    return conn.execute("SELECT * FROM wallets WHERE user_id = ?", (user_id,)).fetchone()


def balance_of(conn: sqlite3.Connection, user_id: str) -> float:
    row = conn.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
    return round(row["balance"], 2) if row else 0.0


def ledger_sum(conn: sqlite3.Connection, user_id: str) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS s FROM transactions WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return round(row["s"], 2)


def post(conn: sqlite3.Connection, user_id: str, kind: str, amount: float, *,
         ride_id: str | None = None, payment_id: str | None = None,
         counterparty_id: str | None = None, platform_fee: float = 0.0,
         note: str = "") -> dict:
    """Append one ledger row and move the cached balance. Caller must hold `atomic()`.

    Raises ValueError if the movement would push the balance negative — wallets
    are prepaid, so a debit can never exceed the balance.
    """
    get_or_create_wallet(conn, user_id)
    current = balance_of(conn, user_id)
    amount = round(amount, 2)
    new_balance = round(current + amount, 2)
    if new_balance < 0:
        raise ValueError(
            f"Insufficient balance: need {abs(amount):.2f} BDT, have {current:.2f} BDT"
        )

    tx_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO transactions
           (id, user_id, kind, amount, platform_fee, balance_after, ride_id,
            payment_id, counterparty_id, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tx_id, user_id, kind, amount, round(platform_fee, 2), new_balance,
         ride_id, payment_id, counterparty_id, note),
    )
    conn.execute(
        "UPDATE wallets SET balance = ?, updated_at = ? WHERE user_id = ?",
        (new_balance, dt.utcnow().isoformat(), user_id),
    )
    return {"id": tx_id, "kind": kind, "amount": amount, "balance_after": new_balance}


# ---------------------------------------------------------------------------
# Ride settlement
# ---------------------------------------------------------------------------

def ride_shares(conn: sqlite3.Connection, ride: sqlite3.Row) -> list[dict]:
    """Seat-weighted share per accepted passenger — the same numbers the cost
    splitter shows the user, so the wallet charges exactly what was displayed."""
    accepted = conn.execute(
        """SELECT rp.passenger_id, rp.seats, u.name
           FROM ride_passengers rp JOIN users u ON rp.passenger_id = u.id
           WHERE rp.ride_id = ? AND rp.status IN ('accepted', 'completed')""",
        (ride["id"],),
    ).fetchall()
    if not accepted:
        return []

    total = round(ride["base_fare"] * ride["surge_multiplier"], 2)
    weights = [max(int(r["seats"]), 1) for r in accepted]
    seat_shares = split_total(total, sum(weights))

    out, i = [], 0
    for r, w in zip(accepted, weights):
        share = round(sum(seat_shares[i:i + w]), 2)
        i += w
        out.append({"passenger_id": r["passenger_id"], "name": r["name"],
                    "seats": w, "share": share})
    return out


def projected_share(conn: sqlite3.Connection, ride: sqlite3.Row, extra_seats: int) -> float:
    """What one more rider taking `extra_seats` would owe — used to block a join
    the rider cannot afford, rather than discovering it after the trip."""
    taken = conn.execute(
        """SELECT COALESCE(SUM(seats), 0) AS s FROM ride_passengers
           WHERE ride_id = ? AND status IN ('accepted', 'completed')""",
        (ride["id"],),
    ).fetchone()["s"]
    total_seats = max(int(taken) + max(extra_seats, 1), 1)
    total = round(ride["base_fare"] * ride["surge_multiplier"], 2)
    shares = split_total(total, total_seats)
    return round(sum(shares[:max(extra_seats, 1)]), 2)


def already_settled(conn: sqlite3.Connection, ride_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM transactions WHERE ride_id = ? AND kind = 'ride_debit' LIMIT 1",
        (ride_id,),
    ).fetchone()
    return row is not None


def settle_ride(conn: sqlite3.Connection, ride: sqlite3.Row) -> dict:
    """Debit every accepted passenger and credit the driver, atomically.

    A passenger whose balance cannot cover their share is recorded as UNSETTLED
    and the driver is not credited for that leg — money is never invented. This
    should be rare because joining is balance-checked, but a fare can rise via
    surge after the join, so the path must exist.
    """
    if already_settled(conn, ride["id"]):
        return {"settled": [], "unsettled": [], "driver_credited": 0.0,
                "platform_fee": 0.0, "status": "already_settled"}

    shares = ride_shares(conn, ride)
    if not shares:
        return {"settled": [], "unsettled": [], "driver_credited": 0.0,
                "platform_fee": 0.0, "status": "no_passengers"}

    settled, unsettled, driver_total, fee_total = [], [], 0.0, 0.0
    with atomic(conn):
        for s in shares:
            note = "Ride " + str(ride["source"]) + " to " + str(ride["destination"])
            try:
                post(conn, s["passenger_id"], "ride_debit", -s["share"],
                     ride_id=ride["id"], counterparty_id=ride["driver_id"],
                     note=note)
            except ValueError as e:
                unsettled.append({**s, "reason": str(e)})
                continue
            fee = round(s["share"] * PLATFORM_COMMISSION_RATE, 2)
            driver_total = round(driver_total + s["share"] - fee, 2)
            fee_total = round(fee_total + fee, 2)
            settled.append(s)

        if driver_total > 0:
            post(conn, ride["driver_id"], "ride_credit", driver_total,
                 ride_id=ride["id"], platform_fee=fee_total,
                 note="Fare from " + str(len(settled)) + " passenger(s)")

    return {
        "settled": settled,
        "unsettled": unsettled,
        "driver_credited": driver_total,
        "platform_fee": fee_total,
        "status": "settled" if settled else "none_settled",
    }

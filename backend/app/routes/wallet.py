"""
Arooohi Backend — Wallet & bKash Routes
Feature 9: Wallet & bKash Integration (mock)

The bKash API is deferred (PROJECT_PLAN.md §2), so top-ups are mocked: we mint a
fake bKash transaction id and credit the wallet immediately. Everything BELOW the
payment gateway is real — balances, the append-only ledger, and the debit guard —
so swapping the mock for the live API later is a change to `_mock_bkash_charge()`
alone, not to the rest of the app.

Ledger invariant: `wallets.balance` is a cache. Every change goes through
`post_transaction()`, which writes a signed `wallet_transactions` row carrying the
resulting `balance_after`, so the balance can always be re-derived from history.
"""
import uuid
from datetime import datetime as dt
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.auth import get_current_user_id

router = APIRouter()

MIN_TOPUP = 10.0
MAX_TOPUP = 25000.0

# Signed-amount convention: which ledger kinds credit vs. debit the wallet.
CREDIT_KINDS = ("topup", "payout", "refund")
DEBIT_KINDS = ("fare", "penalty")


class TopUpRequest(BaseModel):
    amount: float
    method: str = "bkash"
    account: str = ""


def ensure_wallet(conn, user_id: str) -> float:
    """Return the user's balance, creating a zero-balance wallet on first use.
    Callers must hold an open connection; this never commits on its own."""
    row = conn.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        return row["balance"]
    conn.execute("INSERT INTO wallets (user_id, balance) VALUES (?, 0.0)", (user_id,))
    return 0.0


def post_transaction(conn, user_id: str, kind: str, amount: float,
                     ride_id: str | None = None, method: str = "mock",
                     reference: str = "", note: str = "") -> dict:
    """Append one ledger entry and move the cached balance.

    `amount` is always passed POSITIVE; the sign is derived from `kind` so a caller
    can never accidentally credit a penalty. Debits are allowed to overdraw only
    when the caller has already checked affordability — see `charge()`.
    """
    if kind in DEBIT_KINDS:
        signed = -abs(amount)
    elif kind in CREDIT_KINDS:
        signed = abs(amount)
    else:
        raise ValueError(f"unknown ledger kind: {kind}")

    balance = ensure_wallet(conn, user_id)
    new_balance = round(balance + signed, 2)

    tx_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO wallet_transactions
           (id, user_id, kind, amount, balance_after, ride_id, method, reference, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tx_id, user_id, kind, round(signed, 2), new_balance, ride_id, method, reference, note)
    )
    conn.execute("UPDATE wallets SET balance = ? WHERE user_id = ?", (new_balance, user_id))
    return {"id": tx_id, "kind": kind, "amount": round(signed, 2), "balance_after": new_balance}


def charge(conn, user_id: str, amount: float, kind: str, ride_id: str | None = None,
           note: str = "") -> dict:
    """Debit the wallet, allowing the balance to go negative.

    A cancellation penalty (Feature 18) must still be recorded when the student has
    an empty wallet, otherwise cancelling with 0 balance would be free and the
    policy would be trivially bypassable. The negative balance is settled by the
    next top-up.
    """
    return post_transaction(conn, user_id, kind, amount, ride_id=ride_id, note=note)


def _mock_bkash_charge(amount: float, account: str) -> dict:
    """Stand-in for the bKash Tokenized Checkout call. Replace this one function
    with the real gateway request when credentials are available."""
    return {
        "status": "success",
        "trx_id": f"BK{uuid.uuid4().hex[:8].upper()}",
        "amount": round(amount, 2),
        "account": account or "01XXXXXXXXX",
        "processed_at": dt.utcnow().isoformat(),
    }


def _serialize_tx(t) -> dict:
    return {
        "id": t["id"],
        "kind": t["kind"],
        "amount": t["amount"],
        "balance_after": t["balance_after"],
        "ride_id": t["ride_id"],
        "method": t["method"],
        "reference": t["reference"],
        "note": t["note"],
        "created_at": t["created_at"],
    }


@router.get("")
def get_wallet(user_id: str = Depends(get_current_user_id)):
    """Current balance + the 20 most recent ledger entries."""
    conn = get_db()
    balance = ensure_wallet(conn, user_id)
    conn.commit()

    txs = conn.execute(
        """SELECT * FROM wallet_transactions WHERE user_id = ?
           ORDER BY created_at DESC, rowid DESC LIMIT 20""",
        (user_id,)
    ).fetchall()

    totals = conn.execute(
        """SELECT
             COALESCE(SUM(CASE WHEN kind = 'topup'   THEN amount END), 0) AS topped_up,
             COALESCE(SUM(CASE WHEN kind = 'payout'  THEN amount END), 0) AS earned,
             COALESCE(SUM(CASE WHEN kind = 'fare'    THEN -amount END), 0) AS spent,
             COALESCE(SUM(CASE WHEN kind = 'penalty' THEN -amount END), 0) AS penalties
           FROM wallet_transactions WHERE user_id = ?""",
        (user_id,)
    ).fetchone()
    conn.close()

    return {
        "balance": round(balance, 2),
        "currency": "BDT",
        "totals": {
            "topped_up": round(totals["topped_up"], 2),
            "earned": round(totals["earned"], 2),
            "spent": round(totals["spent"], 2),
            "penalties": round(totals["penalties"], 2),
        },
        "transactions": [_serialize_tx(t) for t in txs],
    }


@router.get("/transactions")
def list_transactions(limit: int = 100, user_id: str = Depends(get_current_user_id)):
    """Full ledger history (newest first)."""
    limit = max(1, min(limit, 500))
    conn = get_db()
    txs = conn.execute(
        """SELECT * FROM wallet_transactions WHERE user_id = ?
           ORDER BY created_at DESC, rowid DESC LIMIT ?""",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return {"transactions": [_serialize_tx(t) for t in txs]}


@router.post("/topup")
def top_up(body: TopUpRequest, user_id: str = Depends(get_current_user_id)):
    """Mock bKash top-up — credits the wallet and records the gateway reference."""
    if body.amount is None or body.amount <= 0:
        raise HTTPException(status_code=400, detail="Top-up amount must be positive")
    if body.amount < MIN_TOPUP:
        raise HTTPException(status_code=400, detail=f"Minimum top-up is BDT {MIN_TOPUP:.0f}")
    if body.amount > MAX_TOPUP:
        raise HTTPException(status_code=400, detail=f"Maximum top-up is BDT {MAX_TOPUP:.0f}")
    if body.method not in ("bkash", "mock"):
        raise HTTPException(status_code=400, detail="Unsupported payment method")

    gateway = _mock_bkash_charge(body.amount, body.account)
    if gateway["status"] != "success":
        raise HTTPException(status_code=402, detail="Payment was declined by the provider")

    conn = get_db()
    tx = post_transaction(
        conn, user_id, "topup", body.amount,
        method=body.method, reference=gateway["trx_id"],
        note=f"bKash top-up (mock) from {gateway['account']}",
    )
    conn.commit()
    conn.close()

    return {
        "message": f"BDT {body.amount:.2f} added to your wallet",
        "mocked": True,
        "gateway": gateway,
        "transaction": tx,
        "balance": tx["balance_after"],
    }

"""
Arooohi Backend — Wallet Routes
Feature 9: Wallet & bKash Integration

Prepaid wallet: the gateway is touched only at the edges (top-up in, cash-out
out). Ride settlement is an internal transfer handled in `wallet_service`.

Top-up follows bKash's tokenized-checkout lifecycle:

    POST /api/wallet/topup          -> paymentID + checkout_url  (create)
      ... browser leaves for the gateway's own PIN page ...
    POST /api/wallet/topup/execute  -> credits the wallet        (execute)

The redirect back from the gateway carries a `status` parameter that is NOT
trusted: only the server-side execute call can complete a payment.
"""
import os
import uuid
from datetime import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import wallet_service as ws
from app.auth import get_current_user_id
from app.database import get_db
from app.payments import GatewayError, get_gateway

router = APIRouter()

# Where the gateway sends the browser back to. Configurable so a tunnelled or
# deployed frontend works without a code change (the live gateway requires HTTPS).
FRONTEND_CALLBACK = (
    os.getenv("FRONTEND_PUBLIC_URL", "http://127.0.0.1:3000").rstrip("/")
    + "/wallet/callback"
)


class TopUpRequest(BaseModel):
    amount: float


class ExecuteRequest(BaseModel):
    payment_id: str


class WithdrawRequest(BaseModel):
    amount: float
    wallet_number: str = ""


def _tx_json(r) -> dict:
    return {
        "id": r["id"],
        "kind": r["kind"],
        "amount": round(r["amount"], 2),
        "platform_fee": round(r["platform_fee"], 2),
        "balance_after": round(r["balance_after"], 2),
        "ride_id": r["ride_id"],
        "payment_id": r["payment_id"],
        "note": r["note"],
        "created_at": r["created_at"],
    }


@router.get("")
def get_wallet(user_id: str = Depends(get_current_user_id)):
    """Balance plus the 10 most recent ledger entries."""
    conn = get_db()
    ws.get_or_create_wallet(conn, user_id)
    conn.commit()
    balance = ws.balance_of(conn, user_id)
    rows = conn.execute(
        """SELECT * FROM transactions WHERE user_id = ?
           ORDER BY created_at DESC, rowid DESC LIMIT 10""",
        (user_id,),
    ).fetchall()
    conn.close()
    return {
        "balance": balance,
        "currency": "BDT",
        "recent": [_tx_json(r) for r in rows],
    }


@router.get("/transactions")
def list_transactions(limit: int = 50, user_id: str = Depends(get_current_user_id)):
    """Full ledger history — also the data source for receipts (#10)."""
    limit = max(1, min(limit, 200))
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM transactions WHERE user_id = ?
           ORDER BY created_at DESC, rowid DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [_tx_json(r) for r in rows]


@router.post("/topup")
def start_topup(body: TopUpRequest, user_id: str = Depends(get_current_user_id)):
    """Step 1+2: grant token, then create the payment and hand back a checkout URL."""
    amount = round(body.amount, 2)
    if amount < ws.MIN_TOPUP or amount > ws.MAX_TOPUP:
        raise HTTPException(
            status_code=400,
            detail=f"Top-up must be between {ws.MIN_TOPUP:.0f} and {ws.MAX_TOPUP:.0f} BDT",
        )

    gateway = get_gateway()
    reference = f"AROOOHI-{uuid.uuid4().hex[:10].upper()}"
    try:
        result = gateway.create_payment(amount, reference, FRONTEND_CALLBACK, "topup")
    except GatewayError as e:
        raise HTTPException(status_code=502, detail=f"Payment gateway unavailable: {e}")

    conn = get_db()
    conn.execute(
        """INSERT INTO bkash_payments (id, user_id, amount, intent, status)
           VALUES (?, ?, ?, 'topup', ?)""",
        (result.payment_id, user_id, amount, result.status),
    )
    conn.commit()
    conn.close()

    return {
        "payment_id": result.payment_id,
        "amount": amount,
        "status": result.status,
        "checkout_url": result.checkout_url,
        "gateway": gateway.name,
    }


@router.post("/topup/execute")
def execute_topup(body: ExecuteRequest, user_id: str = Depends(get_current_user_id)):
    """Step 4: the ONLY place a top-up can be credited.

    Idempotent twice over: the gateway returns the same trxID on re-execute, and
    uq_transactions_payment stops a second ledger row for the same paymentID.
    """
    conn = get_db()
    payment = conn.execute(
        "SELECT * FROM bkash_payments WHERE id = ? AND user_id = ?",
        (body.payment_id, user_id),
    ).fetchone()
    if not payment:
        conn.close()
        raise HTTPException(status_code=404, detail="Payment not found")

    existing = conn.execute(
        "SELECT * FROM transactions WHERE payment_id = ?", (body.payment_id,)
    ).fetchone()
    if existing:
        balance = ws.balance_of(conn, user_id)
        conn.close()
        return {"message": "Top-up already credited", "status": "completed",
                "amount": round(existing["amount"], 2), "balance": balance,
                "trx_id": payment["trx_id"], "duplicate": True}

    try:
        result = get_gateway().execute_payment(body.payment_id)
    except GatewayError as e:
        conn.close()
        raise HTTPException(status_code=502, detail=f"Payment gateway unavailable: {e}")

    if not result.is_success:
        conn.execute(
            "UPDATE bkash_payments SET status = ?, failure_reason = ? WHERE id = ?",
            (result.status, result.failure_reason, body.payment_id),
        )
        conn.commit()
        conn.close()
        raise HTTPException(
            status_code=402,
            detail=result.failure_reason or f"Payment {result.status}",
        )

    amount = round(result.amount or payment["amount"], 2)
    try:
        with ws.atomic(conn):
            ws.post(conn, user_id, "topup", amount,
                    payment_id=body.payment_id,
                    note=f"bKash top-up (trx {result.trx_id})")
            conn.execute(
                "UPDATE bkash_payments SET status = 'completed', trx_id = ? WHERE id = ?",
                (result.trx_id, body.payment_id),
            )
    except Exception:
        conn.close()
        raise HTTPException(status_code=500, detail="Could not credit the wallet")

    balance = ws.balance_of(conn, user_id)
    conn.close()
    return {"message": "Top-up successful", "status": "completed", "amount": amount,
            "trx_id": result.trx_id, "balance": balance, "duplicate": False}


@router.get("/payment/{payment_id}")
def payment_status(payment_id: str, user_id: str = Depends(get_current_user_id)):
    """Reconciliation: ask the gateway what really happened to an interrupted payment."""
    conn = get_db()
    payment = conn.execute(
        "SELECT * FROM bkash_payments WHERE id = ? AND user_id = ?",
        (payment_id, user_id),
    ).fetchone()
    if not payment:
        conn.close()
        raise HTTPException(status_code=404, detail="Payment not found")

    try:
        remote = get_gateway().query_payment(payment_id)
    except GatewayError as e:
        conn.close()
        raise HTTPException(status_code=502, detail=f"Payment gateway unavailable: {e}")

    credited = conn.execute(
        "SELECT 1 FROM transactions WHERE payment_id = ? LIMIT 1", (payment_id,)
    ).fetchone() is not None

    if remote.status != payment["status"]:
        conn.execute("UPDATE bkash_payments SET status = ? WHERE id = ?",
                     (remote.status, payment_id))
        conn.commit()
    conn.close()

    return {
        "payment_id": payment_id,
        "local_status": payment["status"],
        "gateway_status": remote.status,
        "credited": credited,
        "amount": round(payment["amount"], 2),
        "failure_reason": remote.failure_reason,
        "recoverable": remote.status == "authorized" and not credited,
    }


@router.post("/withdraw")
def withdraw(body: WithdrawRequest, user_id: str = Depends(get_current_user_id)):
    """Cash out to bKash — the other edge of the prepaid model."""
    amount = round(body.amount, 2)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Withdrawal amount must be positive")

    conn = get_db()
    balance = ws.balance_of(conn, user_id)
    if amount > balance:
        conn.close()
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient balance: you have {balance:.2f} BDT",
        )

    payout_id = "PO" + uuid.uuid4().hex[:12].upper()
    try:
        with ws.atomic(conn):
            ws.post(conn, user_id, "withdrawal", -amount,
                    payment_id=payout_id,
                    note=f"Cash-out to bKash {body.wallet_number or '(unspecified)'}")
            conn.execute(
                """INSERT INTO bkash_payments
                   (id, user_id, amount, intent, status, trx_id, wallet_number)
                   VALUES (?, ?, ?, 'withdrawal', 'completed', ?, ?)""",
                (payout_id, user_id, amount, payout_id, body.wallet_number),
            )
    except ValueError as e:
        conn.close()
        raise HTTPException(status_code=402, detail=str(e))

    new_balance = ws.balance_of(conn, user_id)
    conn.close()
    print(f"\n[bKash PAYOUT] {amount:.2f} BDT -> {body.wallet_number or 'wallet'} "
          f"(ref {payout_id})\n")
    return {"message": f"{amount:.2f} BDT sent to your bKash account",
            "payout_id": payout_id, "balance": new_balance}


@router.get("/reconcile")
def reconcile(user_id: str = Depends(get_current_user_id)):
    """Assert the cached balance still equals the append-only ledger.

    A mismatch means a bug wrote one without the other, and is worth surfacing
    loudly rather than letting it drift silently.
    """
    conn = get_db()
    ws.get_or_create_wallet(conn, user_id)
    conn.commit()
    stored = ws.balance_of(conn, user_id)
    ledger = ws.ledger_sum(conn, user_id)
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM transactions WHERE user_id = ?", (user_id,)
    ).fetchone()["c"]
    conn.close()

    balanced = abs(stored - ledger) < 0.005
    return {
        "stored_balance": stored,
        "ledger_sum": ledger,
        "difference": round(stored - ledger, 2),
        "transaction_count": count,
        "status": "balanced" if balanced else "MISMATCH",
        "checked_at": dt.utcnow().isoformat(),
    }

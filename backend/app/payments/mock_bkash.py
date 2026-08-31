"""
Arooohi Backend — Simulated bKash Gateway (DEMO_MODE=1)
Feature 9: Wallet & bKash Integration

Implements the REAL tokenized-checkout state machine against a local, in-process
"gateway". Everything except the counterparty is genuine: the redirect handoff,
the server-side execute confirmation, the status lifecycle and the trxIDs.

Deterministic test wallet numbers make the failure paths demoable:

    01770000001  -> always succeeds
    01770000002  -> always fails   (insufficient funds at bKash)
    01770000003  -> always times out (payment stays pending; recover via query)
    01770000004  -> user cancels on the PIN screen
    anything else-> succeeds (so demos are easy)

A real gateway does not forget a payment when the merchant's server restarts, so
neither does this one: in-memory state is a cache, and any unknown paymentID is
rehydrated from the `bkash_payments` row that `create_payment` wrote. Without this,
an authorised-but-unexecuted payment became permanently unexecutable after a
restart — and `uvicorn --reload` restarts on every code edit.
"""
import secrets
import threading
import time

from app.payments.base import PaymentGateway, PaymentResult

TEST_NUMBERS = {
    "01770000001": "completed",
    "01770000002": "failed",
    "01770000003": "timeout",
    "01770000004": "cancelled",
}

FAILURE_REASONS = {
    "failed": "Insufficient balance in the bKash account",
    "timeout": "The bKash account did not respond in time",
    "cancelled": "Payment was cancelled by the user",
}

TOKEN_TTL_S = 3600


class MockBkashGateway(PaymentGateway):
    name = "mock-bkash"

    def __init__(self, checkout_base: str):
        self._checkout_base = checkout_base.rstrip("/")
        self._payments: dict[str, dict] = {}
        self._token: tuple[str, float] | None = None
        self._lock = threading.Lock()

    # -- durability ----------------------------------------------------------
    def _rehydrate(self, payment_id: str) -> dict | None:
        """Rebuild a forgotten payment from the row create_payment persisted.

        Caller must hold self._lock. Returns the cache entry, or None if no such
        payment ever existed.
        """
        from app.database import get_db
        try:
            conn = get_db()
            row = conn.execute(
                """SELECT amount, intent, status, trx_id, wallet_number, failure_reason
                   FROM bkash_payments WHERE id = ?""",
                (payment_id,),
            ).fetchone()
            conn.close()
        except Exception:
            return None
        if not row:
            return None
        entry = {
            "status": row["status"],
            "amount": round(row["amount"], 2),
            "intent": row["intent"],
            "reference": payment_id,
            "callback_url": "",
            "trx_id": row["trx_id"],
            "failure_reason": row["failure_reason"] or "",
            "wallet_number": row["wallet_number"] or "",
        }
        self._payments[payment_id] = entry
        return entry

    def _get(self, payment_id: str) -> dict | None:
        """Cache lookup with a persistent fallback. Caller must hold self._lock."""
        return self._payments.get(payment_id) or self._rehydrate(payment_id)

    # -- step 1 -------------------------------------------------------------
    def grant_token(self) -> str:
        """Mirrors the real 1-hour id_token, including the caching behaviour."""
        with self._lock:
            if self._token and self._token[1] > time.time():
                return self._token[0]
            token = "mock_" + secrets.token_urlsafe(24)
            self._token = (token, time.time() + TOKEN_TTL_S)
            return token

    # -- step 2 -------------------------------------------------------------
    def create_payment(self, amount: float, reference: str, callback_url: str,
                       intent: str = "topup") -> PaymentResult:
        self.grant_token()  # the real API requires a valid token here
        payment_id = "TR" + secrets.token_hex(8).upper()
        with self._lock:
            self._payments[payment_id] = {
                "status": "created",
                "amount": round(amount, 2),
                "intent": intent,
                "reference": reference,
                "callback_url": callback_url,
                "trx_id": None,
                "failure_reason": "",
            }
        return PaymentResult(
            payment_id=payment_id,
            status="created",
            amount=round(amount, 2),
            checkout_url=f"{self._checkout_base}/bkash/checkout/{payment_id}",
        )

    # -- step 3 (happens on the gateway's own page) --------------------------
    def authorize(self, payment_id: str, wallet_number: str) -> PaymentResult:
        """Called by the simulated PIN screen. Decides the outcome from the
        test wallet number, exactly like bKash's sandbox test accounts."""
        with self._lock:
            p = self._get(payment_id)
            if not p:
                return PaymentResult(payment_id=payment_id, status="failed",
                                     failure_reason="Unknown paymentID")
            if p["status"] != "created":
                return PaymentResult(payment_id=payment_id, status=p["status"],
                                     amount=p["amount"], trx_id=p["trx_id"],
                                     failure_reason=p["failure_reason"])

            outcome = TEST_NUMBERS.get(wallet_number.strip(), "completed")
            if outcome == "completed":
                # Authorized, but NOT yet completed — completion requires the
                # merchant to call execute_payment(). This split is the point.
                p["status"] = "authorized"
            else:
                p["status"] = "timeout" if outcome == "timeout" else outcome
                p["failure_reason"] = FAILURE_REASONS.get(outcome, "")
            p["wallet_number"] = wallet_number.strip()
            return PaymentResult(payment_id=payment_id, status=p["status"],
                                 amount=p["amount"],
                                 failure_reason=p["failure_reason"])

    # -- step 4 -------------------------------------------------------------
    def execute_payment(self, payment_id: str) -> PaymentResult:
        """The merchant-side confirmation. Only this can complete a payment."""
        with self._lock:
            p = self._get(payment_id)
            if not p:
                return PaymentResult(payment_id=payment_id, status="failed",
                                     failure_reason="Unknown paymentID")

            if p["status"] == "completed":
                # Idempotent: re-executing returns the same trxID rather than
                # creating a second one.
                return PaymentResult(payment_id=payment_id, status="completed",
                                     amount=p["amount"], trx_id=p["trx_id"])

            if p["status"] != "authorized":
                return PaymentResult(payment_id=payment_id, status=p["status"],
                                     amount=p["amount"],
                                     failure_reason=p["failure_reason"] or
                                     "Payment was not authorized by the user")

            p["status"] = "completed"
            p["trx_id"] = secrets.token_hex(5).upper()
            return PaymentResult(payment_id=payment_id, status="completed",
                                 amount=p["amount"], trx_id=p["trx_id"])

    # -- reconciliation ------------------------------------------------------
    def query_payment(self, payment_id: str) -> PaymentResult:
        with self._lock:
            p = self._get(payment_id)
            if not p:
                return PaymentResult(payment_id=payment_id, status="failed",
                                     failure_reason="Unknown paymentID")
            return PaymentResult(payment_id=payment_id, status=p["status"],
                                 amount=p["amount"], trx_id=p["trx_id"],
                                 failure_reason=p["failure_reason"])

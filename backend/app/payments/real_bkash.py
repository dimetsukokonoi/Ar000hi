"""
Arooohi Backend — Live bKash Tokenized Checkout (DEMO_MODE=0)
Feature 9: Wallet & bKash Integration

This is the swap-in target that makes the mock worth building: same interface,
same call order, so nothing outside this file changes.

NOT EXERCISED IN THE DEMO. bKash issues app_key / app_secret / username /
password only through merchant onboarding, and the live gateway requires the
callback URL to be HTTPS — so 127.0.0.1 needs a tunnel. Credentials are read
from the environment and must never be committed:

    BKASH_APP_KEY, BKASH_APP_SECRET, BKASH_USERNAME, BKASH_PASSWORD
    BKASH_BASE_URL   (defaults to the sandbox host)

Uses urllib from the standard library so the project gains no new dependency.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

from app.payments.base import PaymentGateway, PaymentResult, GatewayError

SANDBOX_BASE = "https://tokenized.sandbox.bka.sh/v1.2.0-beta"
TIMEOUT_S = 30  # bKash documents a 30s timeout for all APIs

# bKash's transactionStatus values -> our normalised lifecycle
_STATUS_MAP = {
    "Initiated": "created",
    "Authorized": "authorized",
    "Completed": "completed",
    "Cancelled": "cancelled",
    "Failed": "failed",
}


class RealBkashGateway(PaymentGateway):
    name = "bkash-tokenized"

    def __init__(self):
        self.base = os.getenv("BKASH_BASE_URL", SANDBOX_BASE).rstrip("/")
        self.app_key = os.getenv("BKASH_APP_KEY", "")
        self.app_secret = os.getenv("BKASH_APP_SECRET", "")
        self.username = os.getenv("BKASH_USERNAME", "")
        self.password = os.getenv("BKASH_PASSWORD", "")
        if not all((self.app_key, self.app_secret, self.username, self.password)):
            raise GatewayError(
                "bKash credentials missing. Set BKASH_APP_KEY, BKASH_APP_SECRET, "
                "BKASH_USERNAME and BKASH_PASSWORD, or run with DEMO_MODE=1 to use "
                "the simulated gateway."
            )
        self._token: tuple[str, float] | None = None
        self._lock = threading.Lock()

    def _post(self, path: str, body: dict, headers: dict) -> dict:
        req = urllib.request.Request(
            f"{self.base}{path}", data=json.dumps(body).encode(), method="POST"
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise GatewayError(f"bKash {path} returned HTTP {e.code}") from e
        except Exception as e:
            raise GatewayError(f"bKash {path} unreachable: {e}") from e

    def grant_token(self) -> str:
        with self._lock:
            if self._token and self._token[1] > time.time():
                return self._token[0]
        data = self._post(
            "/tokenized/checkout/token/grant",
            {"app_key": self.app_key, "app_secret": self.app_secret},
            {"username": self.username, "password": self.password},
        )
        token = data.get("id_token")
        if not token:
            raise GatewayError(f"bKash token grant failed: {data}")
        with self._lock:
            # Real tokens live ~1h; refresh a minute early to avoid races.
            self._token = (token, time.time() + int(data.get("expires_in", 3600)) - 60)
        return token

    def _auth_headers(self) -> dict:
        return {"Authorization": self.grant_token(), "X-APP-Key": self.app_key}

    def create_payment(self, amount: float, reference: str, callback_url: str,
                       intent: str = "topup") -> PaymentResult:
        data = self._post(
            "/tokenized/checkout/create",
            {
                "mode": "0011",                     # tokenized checkout
                "payerReference": reference,
                "callbackURL": callback_url,
                "amount": f"{amount:.2f}",
                "currency": "BDT",
                "intent": "sale",
                "merchantInvoiceNumber": reference,
            },
            self._auth_headers(),
        )
        payment_id = data.get("paymentID")
        if not payment_id:
            raise GatewayError(f"bKash create failed: {data}")
        return PaymentResult(
            payment_id=payment_id,
            status=_STATUS_MAP.get(data.get("transactionStatus", ""), "created"),
            amount=amount,
            checkout_url=data.get("bkashURL"),
            raw=data,
        )

    def execute_payment(self, payment_id: str) -> PaymentResult:
        data = self._post("/tokenized/checkout/execute",
                          {"paymentID": payment_id}, self._auth_headers())
        status = _STATUS_MAP.get(data.get("transactionStatus", ""), "failed")
        return PaymentResult(
            payment_id=payment_id,
            status=status,
            amount=float(data.get("amount") or 0),
            trx_id=data.get("trxID"),
            failure_reason=data.get("statusMessage", "") if status != "completed" else "",
            raw=data,
        )

    def query_payment(self, payment_id: str) -> PaymentResult:
        data = self._post("/tokenized/checkout/payment/status",
                          {"paymentID": payment_id}, self._auth_headers())
        status = _STATUS_MAP.get(data.get("transactionStatus", ""), "failed")
        return PaymentResult(
            payment_id=payment_id,
            status=status,
            amount=float(data.get("amount") or 0),
            trx_id=data.get("trxID"),
            failure_reason=data.get("statusMessage", "") if status != "completed" else "",
            raw=data,
        )

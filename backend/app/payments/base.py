"""
Arooohi Backend — Payment Gateway Interface
Feature 9: Wallet & bKash Integration

This mirrors bKash's *tokenized checkout* lifecycle exactly:

    grant_token()    -> short-lived id_token (cached ~1h)
    create_payment() -> paymentID + a checkout URL the browser is sent to
      ... the user authenticates on the GATEWAY's page, never ours ...
    execute_payment()-> trxID + final status   <-- the only trustworthy signal
    query_payment()  -> status lookup, for reconciling interrupted payments

Security note that the whole design exists to enforce: the redirect back from
the gateway carries a `status` query parameter, and it CANNOT be trusted — a
user can type that URL themselves. Money is only ever credited after
`execute_payment()` is called server-side and the gateway confirms.
"""
from dataclasses import dataclass, field


class GatewayError(RuntimeError):
    """Raised when the gateway is unreachable or rejects the request outright."""


@dataclass
class PaymentResult:
    """Normalised result shape shared by every gateway implementation."""
    payment_id: str
    status: str                      # created|authorized|completed|failed|cancelled|timeout
    amount: float = 0.0
    trx_id: str | None = None
    checkout_url: str | None = None
    failure_reason: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == "completed"


class PaymentGateway:
    """Interface implemented by MockBkashGateway and RealBkashGateway."""

    name = "abstract"

    def grant_token(self) -> str:
        raise NotImplementedError

    def create_payment(self, amount: float, reference: str, callback_url: str,
                       intent: str = "topup") -> PaymentResult:
        raise NotImplementedError

    def execute_payment(self, payment_id: str) -> PaymentResult:
        raise NotImplementedError

    def query_payment(self, payment_id: str) -> PaymentResult:
        raise NotImplementedError

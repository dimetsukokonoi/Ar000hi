"""Gateway selection.

Only the simulated gateway is implemented. bKash issues credentials for a live
integration solely through merchant onboarding, so this project has no live
client. Rather than silently falling back to the simulator when someone sets
DEMO_MODE=0 -- which would mean pretending to handle real money -- this fails
loudly, matching how app/auth.py refuses to run on the default SECRET_KEY.
"""
import os
import threading

from app.payments.base import GatewayError, PaymentGateway

_gateway: PaymentGateway | None = None
_lock = threading.Lock()

DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1"
# Where the simulated checkout page is served from (the backend itself).
CHECKOUT_BASE = os.getenv("BACKEND_PUBLIC_URL", "http://127.0.0.1:8000")


def get_gateway() -> PaymentGateway:
    """Process-wide singleton so the mock's in-memory state survives requests."""
    global _gateway
    if _gateway is not None:
        return _gateway
    with _lock:
        if _gateway is None:
            if not DEMO_MODE:
                raise GatewayError(
                    "No live payment gateway is implemented. bKash credentials are "
                    "issued only through merchant onboarding, so this build ships the "
                    "simulated gateway alone. Run with DEMO_MODE=1, or add a live "
                    "client implementing app.payments.base.PaymentGateway."
                )
            from app.payments.mock_bkash import MockBkashGateway
            _gateway = MockBkashGateway(CHECKOUT_BASE)
    return _gateway

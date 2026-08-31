"""Gateway selection — the single place DEMO_MODE decides mock vs live."""
import os
import threading

from app.payments.base import PaymentGateway

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
            if DEMO_MODE:
                from app.payments.mock_bkash import MockBkashGateway
                _gateway = MockBkashGateway(CHECKOUT_BASE)
            else:
                from app.payments.real_bkash import RealBkashGateway
                _gateway = RealBkashGateway()
    return _gateway

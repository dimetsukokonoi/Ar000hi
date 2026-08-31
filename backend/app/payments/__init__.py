"""bKash payment gateway layer (Feature 9).

`get_gateway()` returns the mock or the live client depending on DEMO_MODE, so
routes never import a concrete implementation.
"""
from app.payments.base import PaymentGateway, PaymentResult, GatewayError
from app.payments.factory import get_gateway

__all__ = ["PaymentGateway", "PaymentResult", "GatewayError", "get_gateway"]

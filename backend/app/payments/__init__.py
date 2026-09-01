"""bKash payment gateway layer (Feature 9).

`get_gateway()` returns the gateway implementation, so routes never import a
concrete class. Only the simulated gateway ships with this project.
"""
from app.payments.base import PaymentGateway, PaymentResult, GatewayError
from app.payments.factory import get_gateway

__all__ = ["PaymentGateway", "PaymentResult", "GatewayError", "get_gateway"]

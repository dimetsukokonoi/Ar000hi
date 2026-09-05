"""Validated request data for wallet; no persistence or HTTP handlers."""

from pydantic import BaseModel


class TopUpRequest(BaseModel):
    amount: float


class ExecuteRequest(BaseModel):
    payment_id: str


class WithdrawRequest(BaseModel):
    amount: float
    wallet_number: str = ""

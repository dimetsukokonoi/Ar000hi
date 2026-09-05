"""Wallet controller: HTTP input, authentication and model dispatch."""

from fastapi import APIRouter, Depends
from app.controllers.dependencies import get_current_user_id
from app.models import wallet as model
from app.schemas.wallet import TopUpRequest, ExecuteRequest, WithdrawRequest

router = APIRouter()


@router.get("")
def get_wallet(user_id: str = Depends(get_current_user_id)):
    """Balance plus the 10 most recent ledger entries."""
    return model.get_wallet(user_id=user_id)


@router.get("/transactions")
def list_transactions(limit: int = 50, user_id: str = Depends(get_current_user_id)):
    """Full ledger history — also the data source for receipts (#10)."""
    return model.list_transactions(limit=limit, user_id=user_id)


@router.post("/topup")
def start_topup(body: TopUpRequest, user_id: str = Depends(get_current_user_id)):
    """Step 1+2: grant token, then create the payment and hand back a checkout URL."""
    return model.start_topup(body=body, user_id=user_id)


@router.post("/topup/execute")
def execute_topup(body: ExecuteRequest, user_id: str = Depends(get_current_user_id)):
    """Step 4: the ONLY place a top-up can be credited.

    Idempotent twice over: the gateway returns the same trxID on re-execute, and
    uq_transactions_payment stops a second ledger row for the same paymentID.
    """
    return model.execute_topup(body=body, user_id=user_id)


@router.get("/payment/{payment_id}")
def payment_status(payment_id: str, user_id: str = Depends(get_current_user_id)):
    """Reconciliation: ask the gateway what really happened to an interrupted payment."""
    return model.payment_status(payment_id=payment_id, user_id=user_id)


@router.post("/withdraw")
def withdraw(body: WithdrawRequest, user_id: str = Depends(get_current_user_id)):
    """Cash out to bKash — the other edge of the prepaid model."""
    return model.withdraw(body=body, user_id=user_id)


@router.get("/reconcile")
def reconcile(user_id: str = Depends(get_current_user_id)):
    """Assert the cached balance still equals the append-only ledger.

    A mismatch means a bug wrote one without the other, and is worth surfacing
    loudly rather than letting it drift silently.
    """
    return model.reconcile(user_id=user_id)

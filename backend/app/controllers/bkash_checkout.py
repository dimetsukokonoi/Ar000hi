"""
Arooohi Backend — Simulated bKash Checkout Page (DEMO_MODE only)
Feature 9: Wallet & bKash Integration

This stands in for bKash's own hosted PIN page. It is deliberately served by the
BACKEND (:8000), not the Next.js app (:3000), so the browser genuinely leaves
Arooohi to authenticate — the same handoff a real gateway forces.

Arooohi never sees a PIN in the real flow, and never sees one here either: this
page belongs to the "gateway", and the merchant app only ever learns the outcome
by calling execute_payment() server-side afterwards.

These routes are intentionally UNAUTHENTICATED (a gateway has no Arooohi session)
and are mounted only when DEMO_MODE=1.
"""

import os

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from app.models import bkash_checkout as model
from app.views.checkout import _render

router = APIRouter()

FRONTEND_CALLBACK = (
    os.getenv("FRONTEND_PUBLIC_URL", "http://127.0.0.1:3000").rstrip("/")
    + "/wallet/callback"
)


@router.get("/checkout/{payment_id}", response_class=HTMLResponse)
def checkout_page(payment_id: str, error: str = ""):
    """The gateway's hosted PIN screen."""
    payment = model.get_payment(payment_id)
    if not payment:
        return HTMLResponse(
            _render(payment_id, 0.0, "Unknown payment reference."), status_code=404
        )
    return HTMLResponse(_render(payment_id, payment["amount"], error))


@router.post("/checkout/{payment_id}/confirm")
def confirm(payment_id: str, wallet_number: str = Form(...), pin: str = Form(...)):
    """User authorised on the gateway. Redirect back to the merchant.

    Note what this does NOT do: it never credits anything. It only marks the
    payment authorised and bounces the browser home with a status parameter the
    merchant is expected to distrust and verify.
    """
    result = model.confirm(payment_id, wallet_number)

    return RedirectResponse(
        f"{FRONTEND_CALLBACK}?paymentID={payment_id}&status={result.status}",
        status_code=303,
    )


@router.post("/checkout/{payment_id}/cancel")
def cancel(payment_id: str):
    """User backed out on the gateway's page."""
    model.cancel(payment_id)
    return RedirectResponse(
        f"{FRONTEND_CALLBACK}?paymentID={payment_id}&status=cancelled",
        status_code=303,
    )


@router.get("/test-accounts")
def test_accounts():
    """Documents the deterministic outcomes, mirroring bKash's sandbox test numbers."""
    return model.test_accounts()

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

from app.database import get_db
from app.payments import get_gateway
from app.payments.mock_bkash import TEST_NUMBERS

router = APIRouter()

FRONTEND_CALLBACK = (
    os.getenv("FRONTEND_PUBLIC_URL", "http://127.0.0.1:3000").rstrip("/")
    + "/wallet/callback"
)

_PINK = "#e2136e"  # bKash brand pink, so the handoff is visually obvious

_PAGE = """
<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>bKash Payment</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: system-ui, -apple-system, Segoe UI, sans-serif;
         background:#f4f4f6; display:flex; align-items:center;
         justify-content:center; min-height:100vh; padding:16px; }}
  .card {{ background:#fff; width:100%; max-width:380px; border-radius:12px;
           overflow:hidden; box-shadow:0 8px 32px rgba(0,0,0,.14); }}
  .top {{ background:{pink}; color:#fff; padding:20px 24px; }}
  .brand {{ font-size:1.6rem; font-weight:800; letter-spacing:-.5px; }}
  .sim {{ font-size:.68rem; opacity:.85; margin-top:2px;
          text-transform:uppercase; letter-spacing:.08em; }}
  .body {{ padding:24px; }}
  .row {{ display:flex; justify-content:space-between; font-size:.9rem;
          color:#555; margin-bottom:8px; }}
  .amt {{ font-size:2rem; font-weight:800; color:#222; margin:4px 0 20px; }}
  label {{ display:block; font-size:.78rem; color:#666; margin-bottom:6px;
           font-weight:600; }}
  input {{ width:100%; padding:12px; border:1px solid #ddd; border-radius:8px;
           font-size:1rem; margin-bottom:16px; }}
  input:focus {{ outline:2px solid {pink}; border-color:transparent; }}
  button {{ width:100%; padding:14px; background:{pink}; color:#fff; border:0;
            border-radius:8px; font-size:1rem; font-weight:700; cursor:pointer; }}
  button:hover {{ filter:brightness(1.08); }}
  .cancel {{ background:transparent; color:#888; margin-top:8px;
             font-weight:500; }}
  .hint {{ background:#fff6fa; border:1px solid #ffd9ea; border-radius:8px;
           padding:12px; font-size:.72rem; color:#7a2247; margin-top:18px;
           line-height:1.6; }}
  .hint code {{ background:#fff; padding:1px 5px; border-radius:4px; }}
  .err {{ background:#fdecea; color:#b3261e; padding:10px 12px;
          border-radius:8px; font-size:.82rem; margin-bottom:14px; }}
</style></head>
<body>
  <div class="card">
    <div class="top">
      <div class="brand">bKash</div>
      <div class="sim">Simulated gateway &middot; no real money</div>
    </div>
    <div class="body">
      {error}
      <div class="row"><span>Merchant</span><strong>Arooohi</strong></div>
      <div class="row"><span>Invoice</span><span>{payment_id}</span></div>
      <div class="amt">&#2547; {amount}</div>
      <form method="post" action="/bkash/checkout/{payment_id}/confirm">
        <label>bKash Account Number</label>
        <input name="wallet_number" value="01770000001" required
               inputmode="numeric" autocomplete="off">
        <label>PIN</label>
        <input name="pin" type="password" value="1234" required
               inputmode="numeric" autocomplete="off">
        <button type="submit">Confirm Payment</button>
      </form>
      <form method="post" action="/bkash/checkout/{payment_id}/cancel">
        <button type="submit" class="cancel">Cancel</button>
      </form>
      <div class="hint">
        <strong>Test accounts</strong><br>
        <code>01770000001</code> succeeds &middot;
        <code>01770000002</code> fails<br>
        <code>01770000003</code> times out &middot;
        <code>01770000004</code> cancels
      </div>
    </div>
  </div>
</body></html>
"""


def _render(payment_id: str, amount: float, error: str = "") -> str:
    err_html = f'<div class="err">{error}</div>' if error else ""
    return _PAGE.format(pink=_PINK, payment_id=payment_id,
                        amount=f"{amount:,.2f}", error=err_html)


@router.get("/checkout/{payment_id}", response_class=HTMLResponse)
def checkout_page(payment_id: str, error: str = ""):
    """The gateway's hosted PIN screen."""
    conn = get_db()
    payment = conn.execute(
        "SELECT amount, status FROM bkash_payments WHERE id = ?", (payment_id,)
    ).fetchone()
    conn.close()
    if not payment:
        return HTMLResponse(_render(payment_id, 0.0, "Unknown payment reference."),
                            status_code=404)
    return HTMLResponse(_render(payment_id, payment["amount"], error))


@router.post("/checkout/{payment_id}/confirm")
def confirm(payment_id: str, wallet_number: str = Form(...), pin: str = Form(...)):
    """User authorised on the gateway. Redirect back to the merchant.

    Note what this does NOT do: it never credits anything. It only marks the
    payment authorised and bounces the browser home with a status parameter the
    merchant is expected to distrust and verify.
    """
    gateway = get_gateway()
    result = gateway.authorize(payment_id, wallet_number)

    conn = get_db()
    conn.execute(
        "UPDATE bkash_payments SET status = ?, wallet_number = ?, failure_reason = ? WHERE id = ?",
        (result.status, wallet_number, result.failure_reason, payment_id),
    )
    conn.commit()
    conn.close()

    return RedirectResponse(
        f"{FRONTEND_CALLBACK}?paymentID={payment_id}&status={result.status}",
        status_code=303,
    )


@router.post("/checkout/{payment_id}/cancel")
def cancel(payment_id: str):
    """User backed out on the gateway's page."""
    conn = get_db()
    conn.execute(
        "UPDATE bkash_payments SET status = 'cancelled', failure_reason = ? WHERE id = ?",
        ("Payment was cancelled by the user", payment_id),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(
        f"{FRONTEND_CALLBACK}?paymentID={payment_id}&status=cancelled",
        status_code=303,
    )


@router.get("/test-accounts")
def test_accounts():
    """Documents the deterministic outcomes, mirroring bKash's sandbox test numbers."""
    return {"test_accounts": TEST_NUMBERS, "default": "any other number succeeds"}

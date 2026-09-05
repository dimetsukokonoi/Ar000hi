"""Simulated gateway HTML presentation."""

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
    return _PAGE.format(
        pink=_PINK, payment_id=payment_id, amount=f"{amount:,.2f}", error=err_html
    )

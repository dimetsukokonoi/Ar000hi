"""Receipt presentation: render model data as PDF bytes."""

from datetime import datetime as dt
from zoneinfo import ZoneInfo

BD_TZ = ZoneInfo("Asia/Dhaka")


def _money(v: float) -> str:
    return f"BDT {v:,.2f}"


def _build_pdf(r: dict) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    W = pdf.w - pdf.l_margin - pdf.r_margin

    def rule(gap_before=3, gap_after=3):
        pdf.ln(gap_before)
        y = pdf.get_y()
        pdf.line(pdf.l_margin, y, pdf.l_margin + W, y)
        pdf.ln(gap_after)

    def row(label: str, value: str, bold=False, size=10):
        pdf.set_font("Helvetica", "B" if bold else "", size)
        pdf.cell(W * 0.55, 6, label)
        pdf.set_font("Helvetica", "B" if bold else "", size)
        pdf.cell(W * 0.45, 6, value, align="R", new_x="LMARGIN", new_y="NEXT")

    def heading(text: str):
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(110)
        pdf.cell(0, 5, text.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0)

    # Header
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(W * 0.5, 9, "Arooohi")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(W * 0.5, 9, r["receipt_no"], align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(110)
    pdf.cell(W * 0.5, 5, "BRAC University student ride-sharing")
    pdf.cell(
        W * 0.5,
        5,
        "Issued " + _fmt_dt(r["issued_at"]),
        align="R",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_text_color(0)
    rule()

    status = (
        "PAID"
        if r["fully_paid"]
        else ("PARTIALLY SETTLED" if r["paid"] else "UNSETTLED")
    )
    row(
        "You "
        + ("drove this ride" if r["role"] == "driver" else "rode as a passenger"),
        status,
        bold=True,
    )

    heading("Trip")
    row("Route", f"{r['route']['source']} to {r['route']['destination']}")
    if r["role"] == "passenger":
        row(
            "Your pickup / drop-off",
            f"{r['route']['pickup_stop']} to {r['route']['dropoff_stop']}",
        )
    if r["route"]["stops"]:
        row("Stops", ", ".join(s_["place"] for s_ in r["route"]["stops"]))
    row("Driver", r["driver_name"])
    row("Completed", _fmt_dt(r["ended_at"] or r["when"]))
    if r["distance_km"]:
        row("Distance", f"{r['distance_km']:.1f} km")
    if r["female_only"]:
        row("Ride type", "Female-only")

    heading("Fare")
    row("Base fare", _money(r["fare"]["base_fare"]))
    row("Surge multiplier", f"x{r['fare']['surge_multiplier']}")
    row("Ride total", _money(r["fare"]["total"]))
    if r["fare"]["platform_fee"] > 0:
        row("Platform fee", "-" + _money(r["fare"]["platform_fee"]))

    heading(f"Split across {len(r['breakdown'])} passenger(s)")
    for b in r["breakdown"]:
        row(
            f"{b['name']}  ({b['seats']} seat{'' if b['seats'] == 1 else 's'})",
            _money(b["share"]),
        )

    rule()
    row(
        r["your_line_label"],
        _money(r["your_amount"] if r["paid"] else r["expected_amount"]),
        bold=True,
        size=12,
    )

    if not r["fully_paid"]:
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(150, 90, 0)
        note = (
            f"Partially settled: {_money(r['expected_amount'])} was owed, "
            f"{_money(r['shortfall'])} was never received."
            if r["paid"]
            else "This fare was never settled - the amount above is what was owed."
        )
        pdf.multi_cell(W, 4.5, note)
        pdf.set_text_color(0)

    rule()
    heading("Payment")
    row("Method", r["payment_method"])
    if r["paid_at"]:
        row("Paid at", _fmt_dt(r["paid_at"]))
    if r["transaction_id"]:
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(120)
        pdf.cell(
            W,
            5,
            "Transaction " + str(r["transaction_id"]),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_text_color(0)

    pdf.ln(6)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(130)
    footer = (
        "Thank you for riding with Arooohi."
        + chr(10)
        + "Demo system - no real currency was transferred."
    )
    pdf.multi_cell(W, 4, footer, align="C")
    return bytes(pdf.output())


def _fmt_dt(value) -> str:
    """Render a stored timestamp in Dhaka local time for the printed receipt."""
    if not value:
        return "-"
    text = str(value).strip().replace("T", " ")
    for cut in ("+", "Z"):
        if cut in text[10:]:
            text = text[:10] + text[10:].split(cut)[0]
    text = text.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            naive = dt.strptime(text, fmt)
            break
        except ValueError:
            naive = None
    if naive is None:
        return str(value)
    return (
        naive.replace(tzinfo=ZoneInfo("UTC"))
        .astimezone(BD_TZ)
        .strftime("%d %b %Y, %H:%M")
    )

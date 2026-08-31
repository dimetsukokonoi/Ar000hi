"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { API } from "@/lib/api";

// Feature 10: the receipt document itself.
//
// "Downloadable" is served two ways, both dependency-free:
//   1. Print / Save as PDF  — window.print() with a print stylesheet that strips
//      the app chrome, which is how the plan proposed it (§4, "frontend print/PDF").
//   2. Download .txt        — a Blob + <a download> for a plain-text copy.

interface Share {
  passenger_id: string;
  name: string;
  seats: number;
  share: number;
}

interface Receipt {
  receipt_no: string;
  issued_at: string;
  ride_id: string;
  role: "driver" | "passenger";
  status: string;
  paid: boolean;
  fully_paid: boolean;
  shortfall: number;
  payment_method: string;
  transaction_id: string | null;
  paid_at: string | null;
  driver_name: string;
  route: {
    source: string;
    destination: string;
    pickup_stop: string;
    dropoff_stop: string;
    stops: { sequence: number; place: string; status: string }[];
  };
  when: string | null;
  started_at: string | null;
  ended_at: string | null;
  distance_km: number | null;
  female_only: boolean;
  fare: {
    base_fare: number;
    surge_multiplier: number;
    total: number;
    seats: number | null;
    platform_fee: number;
  };
  your_line_label: string;
  your_amount: number;
  expected_amount: number;
  breakdown: Share[];
}

const taka = (n: number) =>
  "৳" + n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Timestamps arrive in two shapes: SQLite's naive-UTC "YYYY-MM-DD HH:MM:SS"
// (needs a Z) and offset-aware ISO like "...+06:00" (must NOT get one). Appending
// Z unconditionally produced "Invalid Date" on the offset-aware `issued_at`.
const parseTs = (s: string | null): Date | null => {
  if (!s) return null;
  const raw = s.trim();
  const hasTz = /([zZ]|[+-]\d{2}:?\d{2})$/.test(raw);
  const d = new Date(raw.replace(" ", "T") + (hasTz ? "" : "Z"));
  return isNaN(d.getTime()) ? null : d;
};

const fmt = (s: string | null) => {
  const d = parseTs(s);
  return d
    ? d.toLocaleString(undefined,
        { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
    : "—";
};

/** Strip the dashboard chrome when printing so the page prints as a document. */
const PRINT_CSS = `
@media print {
  .sidebar, .no-print { display: none !important; }
  .dashboard-layout { display: block !important; }
  .main-content { margin: 0 !important; padding: 0 !important; width: 100% !important; }
  body, html { background: #fff !important; }
  .receipt-sheet {
    background: #fff !important; color: #111 !important;
    border: none !important; box-shadow: none !important;
    max-width: 100% !important; padding: 0 !important;
  }
  .receipt-sheet * { color: #111 !important; border-color: #ccc !important; }
  .receipt-sheet .rule { border-color: #ccc !important; }
  @page { margin: 18mm; }
}`;

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 16, padding: "5px 0",
                  fontSize: strong ? "1rem" : "0.86rem" }}>
      <span style={{ color: strong ? "var(--text-primary)" : "var(--text-secondary)",
                     fontWeight: strong ? 700 : 400 }}>{label}</span>
      <span style={{ color: "var(--text-primary)", fontWeight: strong ? 800 : 600,
                     textAlign: "right" }}>{value}</span>
    </div>
  );
}

export default function ReceiptPage() {
  const params = useParams<{ rideId: string }>();
  const rideId = params.rideId;
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token]
  );

  const fetchReceipt = useCallback(async () => {
    const res = await fetch(`${API}/history/${rideId}/receipt`, { headers });
    if (res.status === 403) throw new Error("You were not part of this ride, so its receipt is unavailable.");
    if (res.status === 404) throw new Error("That ride no longer exists.");
    if (!res.ok) throw new Error("Could not load the receipt.");
    return (await res.json()) as Receipt;
  }, [rideId, headers]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchReceipt()
      .then(r => { if (!cancelled) setReceipt(r); })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); });
    return () => { cancelled = true; };
  }, [token, fetchReceipt]);

  const asText = (r: Receipt) => {
    const L: string[] = [];
    L.push("AROOOHI — RIDE RECEIPT");
    L.push("BRAC University student ride-sharing");
    L.push("=".repeat(46));
    L.push(`Receipt no : ${r.receipt_no}`);
    L.push(`Issued     : ${fmt(r.issued_at)}`);
    L.push(`Your role  : ${r.role}`);
    L.push(`Status     : ${r.paid ? "PAID" : "UNSETTLED"}`);
    L.push("");
    L.push("TRIP");
    L.push(`  Route     : ${r.route.source} -> ${r.route.destination}`);
    if (r.role === "passenger")
      L.push(`  You       : ${r.route.pickup_stop} -> ${r.route.dropoff_stop}`);
    if (r.route.stops.length)
      L.push(`  Stops     : ${r.route.stops.map(s => s.place).join(" -> ")}`);
    L.push(`  Driver    : ${r.driver_name}`);
    L.push(`  Completed : ${fmt(r.ended_at || r.when)}`);
    if (r.distance_km) L.push(`  Distance  : ${r.distance_km.toFixed(1)} km`);
    L.push("");
    L.push("FARE");
    L.push(`  Base fare        : ${taka(r.fare.base_fare)}`);
    L.push(`  Surge multiplier : x${r.fare.surge_multiplier}`);
    L.push(`  Ride total       : ${taka(r.fare.total)}`);
    if (r.fare.platform_fee > 0) L.push(`  Platform fee     : -${taka(r.fare.platform_fee)}`);
    L.push("");
    L.push("SPLIT");
    r.breakdown.forEach(b =>
      L.push(`  ${b.name} (${b.seats} seat${b.seats === 1 ? "" : "s"}) : ${taka(b.share)}`));
    L.push("");
    L.push(`${r.your_line_label.toUpperCase()} : ${taka(r.paid ? r.your_amount : r.expected_amount)}`);
    L.push(`Payment method : ${r.payment_method}`);
    if (r.transaction_id) L.push(`Transaction    : ${r.transaction_id}`);
    if (!r.paid) L.push("NOTE: this fare was never settled - the amount above is what was owed.");
    else if (!r.fully_paid)
      L.push(`NOTE: partially settled - ${taka(r.expected_amount)} owed, ${taka(r.shortfall)} never received.`);
    L.push("");
    L.push("=".repeat(46));
    L.push("Demo system — no real currency was transferred.");
    return L.join("\n");
  };

  const download = () => {
    if (!receipt) return;
    const blob = new Blob([asText(receipt)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${receipt.receipt_no}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (error) {
    return (
      <div>
        <div className="glass-card" style={{ padding: 24, color: "var(--danger)", marginBottom: 16 }}>
          ⚠️ {error}
        </div>
        <Link href="/dashboard/history" className="btn btn-ghost">← Back to history</Link>
      </div>
    );
  }
  if (!receipt) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 64 }}>
        <span className="spinner spinner-lg" />
      </div>
    );
  }

  const r = receipt;
  // Partially settled rides show what was actually received; the shortfall is
  // called out in the note below rather than hidden inside one number.
  const shown = r.paid ? r.your_amount : r.expected_amount;

  return (
    <div>
      <style>{PRINT_CSS}</style>

      <div className="no-print" style={{ display: "flex", justifyContent: "space-between",
                                         alignItems: "center", marginBottom: 20, gap: 12, flexWrap: "wrap" }}>
        <Link href="/dashboard/history" className="btn btn-ghost btn-sm">← Back to history</Link>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => window.print()} className="btn btn-primary btn-sm">
            🖨️ Print / Save as PDF
          </button>
          <button onClick={download} className="btn btn-secondary btn-sm">⬇️ Download .txt</button>
        </div>
      </div>

      <div className="glass-card receipt-sheet" style={{ padding: 32, maxWidth: 700, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start",
                      gap: 16, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--primary)" }}>Arooohi</div>
            <div style={{ fontSize: "0.76rem", color: "var(--text-tertiary)" }}>
              BRAC University student ride-sharing
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.72rem", color: "var(--text-tertiary)", textTransform: "uppercase",
                          letterSpacing: "0.08em", fontWeight: 600 }}>Receipt</div>
            <div style={{ fontWeight: 700, color: "var(--text-primary)" }}>{r.receipt_no}</div>
            <div style={{ fontSize: "0.72rem", color: "var(--text-tertiary)" }}>Issued {fmt(r.issued_at)}</div>
          </div>
        </div>

        <div className="rule" style={{ borderTop: "1px solid var(--surface-border)", margin: "20px 0" }} />

        {/* Status */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                      gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          <span className={`badge ${r.role === "driver" ? "badge-primary" : "badge-info"}`}>
            {r.role === "driver" ? "🚗 You drove" : "🧍 You rode"}
          </span>
          <span className={`badge ${r.fully_paid ? "badge-success" : "badge-warning"}`}>
            {r.fully_paid ? "✅ Paid" : r.paid ? "⚠️ Partially settled" : "⚠️ Unsettled"}
          </span>
        </div>

        {/* Trip */}
        <h3 style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.08em",
                     color: "var(--text-tertiary)", marginBottom: 8 }}>Trip</h3>
        <Row label="Route" value={`${r.route.source} → ${r.route.destination}`} />
        {r.role === "passenger" && (
          <Row label="Your pickup → drop-off"
               value={`${r.route.pickup_stop} → ${r.route.dropoff_stop}`} />
        )}
        {r.route.stops.length > 0 && (
          <Row label="Stops" value={r.route.stops.map(s => s.place).join(" → ")} />
        )}
        <Row label="Driver" value={r.driver_name} />
        <Row label="Completed" value={fmt(r.ended_at || r.when)} />
        {r.distance_km ? <Row label="Distance" value={`${r.distance_km.toFixed(1)} km`} /> : null}
        {r.female_only && <Row label="Ride type" value="🌸 Female-only" />}

        <div className="rule" style={{ borderTop: "1px solid var(--surface-border)", margin: "20px 0" }} />

        {/* Fare */}
        <h3 style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.08em",
                     color: "var(--text-tertiary)", marginBottom: 8 }}>Fare</h3>
        <Row label="Base fare" value={taka(r.fare.base_fare)} />
        <Row label="Surge multiplier" value={`×${r.fare.surge_multiplier}`} />
        <Row label="Ride total" value={taka(r.fare.total)} />
        {r.fare.platform_fee > 0 && <Row label="Platform fee" value={`−${taka(r.fare.platform_fee)}`} />}

        {/* Split */}
        <h3 style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.08em",
                     color: "var(--text-tertiary)", margin: "16px 0 8px" }}>
          Split across {r.breakdown.length} passenger{r.breakdown.length === 1 ? "" : "s"}
        </h3>
        {r.breakdown.map(b => (
          <Row key={b.passenger_id}
               label={`${b.name} · ${b.seats} seat${b.seats === 1 ? "" : "s"}`}
               value={taka(b.share)} />
        ))}

        <div className="rule" style={{ borderTop: "2px solid var(--surface-border)", margin: "16px 0" }} />

        <Row label={r.your_line_label} value={taka(shown)} strong />

        {!r.fully_paid && (
          <div style={{ marginTop: 12, padding: "10px 14px", borderLeft: "3px solid var(--warning)",
                        fontSize: "0.78rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
            {r.paid ? (
              <>
                <strong>Partially settled.</strong> {taka(r.expected_amount)} was owed but only{" "}
                {taka(r.your_amount)} was received — a shortfall of{" "}
                <strong>{taka(r.shortfall)}</strong>, because one or more passengers could not
                cover their share. Only the amount actually received counts towards your wallet
                and earnings.
              </>
            ) : (
              <>
                This fare was never settled — the amount shown is what was owed, not what was
                transferred. It is excluded from wallet and earnings totals.
              </>
            )}
          </div>
        )}

        <div className="rule" style={{ borderTop: "1px solid var(--surface-border)", margin: "20px 0" }} />

        <Row label="Payment method" value={r.payment_method} />
        {r.paid_at && <Row label="Paid at" value={fmt(r.paid_at)} />}
        {r.transaction_id && (
          <div style={{ display: "flex", justifyContent: "space-between", gap: 16, padding: "5px 0",
                        fontSize: "0.72rem" }}>
            <span style={{ color: "var(--text-secondary)" }}>Transaction</span>
            <code style={{ color: "var(--text-tertiary)", wordBreak: "break-all" }}>{r.transaction_id}</code>
          </div>
        )}

        <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--surface-border)",
                      fontSize: "0.7rem", color: "var(--text-tertiary)", textAlign: "center",
                      lineHeight: 1.7 }}>
          Thank you for riding with Arooohi.<br />
          Demo system — no real currency was transferred.
        </div>
      </div>
    </div>
  );
}

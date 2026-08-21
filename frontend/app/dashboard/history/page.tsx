"use client";
import { useState, useEffect, useCallback } from "react";

import { API } from "@/lib/api";

// Feature 10: Ride History & Receipt Log
// Feature 7:  Driver Rating & Review (the post-ride prompt lives here, next to
//             the trip it refers to, so rating never needs a separate screen)

interface Trip {
  ride_id: string;
  role: "driver" | "passenger";
  source: string;
  destination: string;
  status: string;
  driver_name: string;
  distance_km: number | null;
  base_fare: number;
  surge_multiplier: number;
  ride_total: number;
  amount: number | null;
  seats: number | null;
  penalty_paid: number;
  scheduled_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  cancelled_at: string | null;
  created_at: string | null;
}

interface HistoryData {
  trips: Trip[];
  summary: {
    total_trips: number;
    completed: number;
    cancelled: number;
    as_driver: number;
    as_passenger: number;
    total_km: number;
    total_spent: number;
    total_penalties: number;
  };
}

interface ReceiptLine { label: string; amount: number }

interface Receipt {
  receipt_no: string;
  issued_to: { name: string; email: string };
  role: string;
  ride: {
    ride_id: string; source: string; destination: string; status: string;
    driver_name: string; distance_km: number | null; base_fare: number;
    surge_multiplier: number; ride_total: number;
    started_at: string | null; ended_at: string | null; cancelled_at: string | null;
  };
  lines: ReceiptLine[];
  amount_due: number;
  currency: string;
}

interface PendingReview {
  ride_id: string;
  source: string;
  destination: string;
  ended_at: string | null;
  driver_id: string;
  driver_name: string;
}

const STATUS_BADGE: Record<string, string> = {
  completed: "badge-success",
  cancelled: "badge-danger",
};

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "—";

export default function HistoryPage() {
  const [data, setData] = useState<HistoryData | null>(null);
  const [pending, setPending] = useState<PendingReview[]>([]);
  const [filter, setFilter] = useState<"all" | "driver" | "passenger">("all");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [reviewing, setReviewing] = useState<PendingReview | null>(null);
  const [stars, setStars] = useState(5);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [error, setError] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const showNotice = (type: "success" | "error", text: string) => {
    setNotice({ type, text });
    setTimeout(() => setNotice(null), 4000);
  };

  // setState only inside promise callbacks — never synchronously in the effect body.
  const load = useCallback(() => {
    if (!token) return;
    Promise.all([
      fetch(`${API}/history`, { headers }).then(r => (r.ok ? r.json() : Promise.reject(new Error("failed")))),
      fetch(`${API}/reviews/pending`, { headers })
        .then(r => (r.ok ? r.json() : { pending: [] }))
        .catch(() => ({ pending: [] })),
    ])
      .then(([h, p]) => {
        setData(h);
        setPending(Array.isArray(p?.pending) ? p.pending : []);
      })
      .catch(() => setError("Could not load your ride history right now."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const openReceipt = async (rideId: string) => {
    try {
      const res = await fetch(`${API}/history/${rideId}/receipt`, { headers });
      const body = await res.json();
      if (res.ok) setReceipt(body);
      else showNotice("error", body.detail || "Could not load that receipt");
    } catch {
      showNotice("error", "Network error — could not load the receipt");
    }
  };

  const submitReview = async () => {
    if (!reviewing) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/reviews`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          ride_id: reviewing.ride_id,
          reviewee_id: reviewing.driver_id,
          stars,
          comment,
        }),
      });
      const body = await res.json();
      if (res.ok) {
        showNotice("success", body.message);
        setReviewing(null);
        setStars(5);
        setComment("");
        load();
      } else {
        showNotice("error", body.detail || "Could not post your review");
      }
    } catch {
      showNotice("error", "Network error — could not post your review");
    } finally {
      setSubmitting(false);
    }
  };

  const trips = (data?.trips ?? []).filter(t => filter === "all" || t.role === filter);

  return (
    <>
      {/* Only the receipt itself reaches the printer. */}
      <style>{`
        @media print {
          body * { visibility: hidden !important; }
          #printable-receipt, #printable-receipt * { visibility: visible !important; }
          #printable-receipt {
            position: absolute; left: 0; top: 0; width: 100%;
            background: #fff !important; color: #000 !important;
            border: none !important; box-shadow: none !important; padding: 24px !important;
          }
          #printable-receipt .no-print { display: none !important; }
        }
      `}</style>

      <div className="page-header">
        <h1 className="page-title">🧾 Ride History & Receipts</h1>
        <p className="page-subtitle">Every trip you have taken or driven, with a printable receipt for each</p>
      </div>

      {notice && (
        <div className={`toast toast-${notice.type}`} style={{ marginBottom: 20 }}>
          <span>{notice.type === "success" ? "✅" : "⚠️"}</span>
          <span>{notice.text}</span>
        </div>
      )}

      {error && (
        <div className="glass-card" style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
          <div style={{ fontSize: "3rem", marginBottom: 16 }}>⚠️</div>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)" }}>{error}</div>
        </div>
      )}

      {!error && !data && (
        <div style={{ display: "flex", justifyContent: "center", padding: 48 }}>
          <span className="spinner spinner-lg" />
        </div>
      )}

      {/* Feature 7: post-ride rating prompt */}
      {pending.length > 0 && (
        <div className="glass-card" style={{ padding: 20, marginBottom: 24, border: "1px solid rgba(245,158,11,0.35)" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 4 }}>⭐ Rate your recent drivers</h3>
          <div style={{ fontSize: "0.78rem", color: "var(--text-tertiary)", marginBottom: 12 }}>
            {pending.length} completed {pending.length === 1 ? "trip is" : "trips are"} waiting for your review.
          </div>
          {pending.map(p => (
            <div
              key={p.ride_id}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                gap: 12, padding: "10px 0", borderBottom: "1px solid rgba(100,120,200,0.06)", flexWrap: "wrap",
              }}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: "0.88rem" }}>{p.driver_name}</div>
                <div style={{ fontSize: "0.74rem", color: "var(--text-tertiary)" }}>
                  {p.source} ➜ {p.destination} · {fmtDate(p.ended_at)}
                </div>
              </div>
              <button className="btn btn-sm btn-primary" onClick={() => setReviewing(p)}>
                Rate driver
              </button>
            </div>
          ))}
        </div>
      )}

      {data && (
        <>
          <div className="stats-grid" style={{ marginBottom: 24 }}>
            <div className="glass-card stat-card">
              <div className="stat-icon" style={{ background: "var(--primary-muted)" }}>🚗</div>
              <div className="stat-value">{data.summary.total_trips}</div>
              <div className="stat-label">Total trips</div>
            </div>
            <div className="glass-card stat-card">
              <div className="stat-icon" style={{ background: "var(--info-muted)" }}>🛣️</div>
              <div className="stat-value">{data.summary.total_km} <span style={{ fontSize: "0.8rem", fontWeight: 500 }}>km</span></div>
              <div className="stat-label">Distance travelled</div>
            </div>
            <div className="glass-card stat-card">
              <div className="stat-icon" style={{ background: "var(--accent-muted)" }}>💸</div>
              <div className="stat-value">৳{data.summary.total_spent.toFixed(0)}</div>
              <div className="stat-label">Spent as a passenger</div>
            </div>
            <div className="glass-card stat-card">
              <div className="stat-icon" style={{ background: "var(--danger-muted)" }}>⚠️</div>
              <div className="stat-value">{data.summary.cancelled}</div>
              <div className="stat-label">Cancelled ({`৳${data.summary.total_penalties.toFixed(0)} in fees`})</div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
            {([
              ["all", `All (${data.summary.total_trips})`],
              ["passenger", `As passenger (${data.summary.as_passenger})`],
              ["driver", `As driver (${data.summary.as_driver})`],
            ] as const).map(([key, label]) => (
              <button
                key={key}
                className={`btn btn-sm ${filter === key ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setFilter(key)}
              >
                {label}
              </button>
            ))}
          </div>

          {trips.length === 0 && (
            <div className="glass-card" style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
              <div style={{ fontSize: "3rem", marginBottom: 16 }}>🧾</div>
              <div style={{ fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>No past trips yet</div>
              <div style={{ fontSize: "0.85rem" }}>Finished rides and their receipts will appear here</div>
            </div>
          )}

          {trips.map(t => (
            <div key={t.ride_id} className="glass-card" style={{ padding: 18, marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "flex-start" }}>
                <div style={{ minWidth: 200 }}>
                  <div style={{ fontWeight: 700, fontSize: "1rem", marginBottom: 4 }}>
                    📍 {t.source} ➜ 🏁 {t.destination}
                  </div>
                  <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", display: "flex", gap: 10, flexWrap: "wrap" }}>
                    <span className={`badge ${STATUS_BADGE[t.status] || "badge-info"}`} style={{ fontSize: "0.68rem" }}>
                      {t.status}
                    </span>
                    <span className="badge badge-info" style={{ fontSize: "0.68rem" }}>
                      {t.role === "driver" ? "🚘 you drove" : "🧍 you rode"}
                    </span>
                    {t.surge_multiplier > 1 && (
                      <span className="badge badge-danger" style={{ fontSize: "0.68rem" }}>⚡ ×{t.surge_multiplier}</span>
                    )}
                  </div>
                  <div style={{ fontSize: "0.74rem", color: "var(--text-tertiary)", marginTop: 6 }}>
                    {t.status === "cancelled" ? fmtDate(t.cancelled_at || t.created_at) : fmtDate(t.ended_at)}
                    {t.distance_km ? ` · ${t.distance_km} km` : ""}
                    {t.role === "passenger" ? ` · driver ${t.driver_name}` : ""}
                  </div>
                </div>

                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "1.15rem", fontWeight: 800 }}>
                    ৳{(t.amount ?? 0).toFixed(2)}
                  </div>
                  {t.penalty_paid > 0 && (
                    <div style={{ fontSize: "0.74rem", color: "var(--danger)", fontWeight: 600 }}>
                      + ৳{t.penalty_paid.toFixed(2)} fee
                    </div>
                  )}
                  <button
                    className="btn btn-sm btn-ghost"
                    style={{ marginTop: 8 }}
                    onClick={() => openReceipt(t.ride_id)}
                  >
                    View receipt
                  </button>
                </div>
              </div>
            </div>
          ))}
        </>
      )}

      {/* Receipt modal */}
      {receipt && (
        <div className="modal-backdrop" onClick={() => setReceipt(null)}>
          <div className="modal" id="printable-receipt" onClick={e => e.stopPropagation()}>
            <div style={{ borderBottom: "1px dashed var(--surface-border)", paddingBottom: 14, marginBottom: 14 }}>
              <div className="modal-title" style={{ marginBottom: 2 }}>Arooohi — Ride Receipt</div>
              <div style={{ fontSize: "0.78rem", color: "var(--text-tertiary)" }}>
                {receipt.receipt_no} · issued to {receipt.issued_to.name}
              </div>
            </div>

            <div style={{ fontSize: "0.84rem", marginBottom: 14, lineHeight: 1.9 }}>
              <div><strong>Route:</strong> {receipt.ride.source} ➜ {receipt.ride.destination}</div>
              <div><strong>Driver:</strong> {receipt.ride.driver_name}</div>
              <div><strong>Status:</strong> {receipt.ride.status}</div>
              {receipt.ride.distance_km != null && <div><strong>Distance:</strong> {receipt.ride.distance_km} km</div>}
              <div><strong>Date:</strong> {fmtDate(receipt.ride.ended_at || receipt.ride.cancelled_at || receipt.ride.started_at)}</div>
            </div>

            <div style={{ borderTop: "1px dashed var(--surface-border)", paddingTop: 12 }}>
              {receipt.lines.map((l, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: "0.85rem" }}>
                  <span style={{ color: "var(--text-secondary)" }}>{l.label}</span>
                  <span style={{ fontWeight: 600 }}>৳{l.amount.toFixed(2)}</span>
                </div>
              ))}
              <div
                style={{
                  display: "flex", justifyContent: "space-between", padding: "12px 0 0",
                  marginTop: 8, borderTop: "2px solid var(--surface-border)",
                  fontSize: "1rem", fontWeight: 800,
                }}
              >
                <span>Amount due</span>
                <span>৳{receipt.amount_due.toFixed(2)} {receipt.currency}</span>
              </div>
            </div>

            <div style={{ fontSize: "0.7rem", color: "var(--text-tertiary)", marginTop: 16, textAlign: "center" }}>
              Thank you for carpooling with Arooohi · BRAC University
            </div>

            <div className="modal-actions no-print" style={{ marginTop: 20 }}>
              <button className="btn btn-ghost" onClick={() => setReceipt(null)}>Close</button>
              <button className="btn btn-primary" onClick={() => window.print()}>🖨 Print / Save PDF</button>
            </div>
          </div>
        </div>
      )}

      {/* Review modal */}
      {reviewing && (
        <div className="modal-backdrop" onClick={() => setReviewing(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">Rate {reviewing.driver_name}</div>
            <div className="modal-text">
              {reviewing.source} ➜ {reviewing.destination} · {fmtDate(reviewing.ended_at)}
            </div>

            <div style={{ display: "flex", gap: 8, justifyContent: "center", marginBottom: 20 }}>
              {[1, 2, 3, 4, 5].map(s => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStars(s)}
                  aria-label={`${s} star${s === 1 ? "" : "s"}`}
                  style={{
                    background: "none", border: "none", cursor: "pointer",
                    fontSize: "2rem", lineHeight: 1,
                    filter: s <= stars ? "none" : "grayscale(1)",
                    opacity: s <= stars ? 1 : 0.35,
                    transition: "transform 0.15s ease",
                  }}
                >
                  ⭐
                </button>
              ))}
            </div>

            <div className="input-group">
              <label className="input-label">Comment (optional)</label>
              <textarea
                className="textarea"
                rows={3}
                maxLength={500}
                placeholder="How was the ride? Was the driver punctual and safe?"
                value={comment}
                onChange={e => setComment(e.target.value)}
              />
            </div>

            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setReviewing(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={submitReview} disabled={submitting}>
                {submitting ? <span className="spinner" /> : "Post review"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

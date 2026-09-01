"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { API } from "@/lib/api";

// Feature 10: Ride History & Receipt Log
// Covers BOTH roles — #16 Earnings answers "what did I earn as a driver", this
// answers "where have I been and what did it cost me", for riders too.

interface Trip {
  ride_id: string;
  role: "driver" | "passenger";
  source: string;
  destination: string;
  status: string;
  when: string | null;
  distance_km: number | null;
  passengers: number;
  counterparty: string;
  amount: number;
  settled: boolean;
  female_only: boolean;
  receipt_no: string;
}

interface Summary {
  trips_as_driver: number;
  trips_as_passenger: number;
  total_trips: number;
  total_spent: number;
  total_earned: number;
  net: number;
  distance_km: number;
}

type Filter = "all" | "driver" | "passenger";

// Feature 7: a completed ride this rider has not rated yet.
interface PendingReview {
  ride_id: string;
  driver_id: string;
  driver_name: string;
  source: string;
  destination: string;
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

const when = (s: string | null) => {
  const d = parseTs(s);
  return d
    ? d.toLocaleString(undefined,
        { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
    : "—";
};

export default function HistoryPage() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // Feature 7: Driver Rating & Review
  const [pending, setPending] = useState<PendingReview[]>([]);
  const [rateTarget, setRateTarget] = useState<PendingReview | null>(null);
  const [stars, setStars] = useState(5);
  const [comment, setComment] = useState("");
  const [rating, setRating] = useState(false);
  const [rateNotice, setRateNotice] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token]
  );

  const fetchAll = useCallback(async (role: Filter) => {
    const [t, s, pr] = await Promise.all([
      fetch(`${API}/history?role=${role}&limit=100`, { headers }).then(r => r.json()),
      fetch(`${API}/history/summary`, { headers }).then(r => r.json()),
      fetch(`${API}/reviews/pending`, { headers }).then(r => r.json()),
    ]);
    return {
      t: (Array.isArray(t) ? t : []) as Trip[],
      s: s as Summary,
      pr: (Array.isArray(pr) ? pr : []) as PendingReview[],
    };
  }, [headers]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchAll(filter)
      .then(({ t, s, pr }) => {
        if (cancelled) return;
        setTrips(t);
        setSummary(s);
        setPending(pr);
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) { setError("Could not load your ride history."); setLoading(false); }
      });
    return () => { cancelled = true; };
  }, [token, filter, fetchAll]);

  const submitReview = async () => {
    if (!rateTarget) return;
    setRating(true);
    try {
      const res = await fetch(`${API}/reviews`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          ride_id: rateTarget.ride_id,
          reviewee_id: rateTarget.driver_id,
          stars,
          comment,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not save your review");
      setRateNotice(`Thanks — you rated ${rateTarget.driver_name} ${stars} star${stars === 1 ? "" : "s"}.`);
      setPending(prev => prev.filter(x => x.ride_id !== rateTarget.ride_id));
      setRateTarget(null);
      setStars(5);
      setComment("");
    } catch (e) {
      setRateNotice(e instanceof Error ? e.message : String(e));
    } finally {
      setRating(false);
    }
  };

  if (error) {
    return <div className="glass-card" style={{ padding: 24, color: "var(--danger)" }}>⚠️ {error}</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">🧾 Ride History</h1>
        <p className="page-subtitle">Every trip you have taken or driven, with a receipt for each.</p>
      </div>

      {summary && (
        <div className="stats-grid" style={{ marginBottom: 20 }}>
          <div className="glass-card" style={{ padding: 20 }}>
            <div className="stat-label">Total Trips</div>
            <div className="stat-value">{summary.total_trips}</div>
            <div style={{ fontSize: "0.76rem", color: "var(--text-tertiary)", marginTop: 4 }}>
              {summary.trips_as_driver} driven · {summary.trips_as_passenger} ridden
            </div>
          </div>
          <div className="glass-card" style={{ padding: 20 }}>
            <div className="stat-label">Spent as Rider</div>
            <div className="stat-value" style={{ color: "var(--danger)" }}>{taka(summary.total_spent)}</div>
          </div>
          <div className="glass-card" style={{ padding: 20 }}>
            <div className="stat-label">Earned as Driver</div>
            <div className="stat-value" style={{ color: "var(--success)" }}>{taka(summary.total_earned)}</div>
          </div>
          <div className="glass-card" style={{ padding: 20 }}>
            <div className="stat-label">Distance Travelled</div>
            <div className="stat-value">{summary.distance_km.toFixed(1)} km</div>
            <div style={{ fontSize: "0.76rem", color: "var(--text-tertiary)", marginTop: 4 }}>
              Net {summary.net >= 0 ? "+" : "−"}{taka(Math.abs(summary.net))}
            </div>
          </div>
        </div>
      )}

      {rateNotice && (
        <div style={{ padding: "10px 14px", marginBottom: 16, borderRadius: "var(--radius-md)",
                      background: "var(--success-muted)", color: "var(--success)", fontSize: "0.85rem" }}>
          {rateNotice}
        </div>
      )}

      {/* Feature 7: post-ride prompt — asked once per ride, then it goes away */}
      {pending.length > 0 && (
        <div className="glass-card" style={{ padding: 18, marginBottom: 20,
                                             borderLeft: "3px solid var(--warning)" }}>
          <div style={{ fontWeight: 700, fontSize: "0.92rem", marginBottom: 10 }}>
            ⭐ Rate your recent {pending.length === 1 ? "ride" : "rides"}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {pending.slice(0, 3).map(pr => (
              <div key={pr.ride_id} style={{ display: "flex", justifyContent: "space-between",
                                             alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  <strong style={{ color: "var(--text-primary)" }}>{pr.driver_name}</strong>
                  {" · "}{pr.source} → {pr.destination}
                </div>
                <button className="btn btn-sm btn-primary" onClick={() => setRateTarget(pr)}>
                  Rate driver
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {(["all", "driver", "passenger"] as Filter[]).map(f => (
          <button
            key={f}
            onClick={() => { setFilter(f); setLoading(true); }}
            className={`btn btn-sm ${filter === f ? "btn-primary" : "btn-ghost"}`}
          >
            {f === "all" ? "All trips" : f === "driver" ? "🚗 As driver" : "🧍 As rider"}
          </button>
        ))}
      </div>

      <div className="glass-card" style={{ padding: 24 }}>
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
            <span className="spinner spinner-lg" />
          </div>
        ) : trips.length === 0 ? (
          <p style={{ color: "var(--text-tertiary)", fontSize: "0.9rem" }}>
            No completed trips yet. Once a ride finishes it appears here with a receipt.{" "}
            <Link href="/dashboard/rides" style={{ color: "var(--primary)" }}>Find a ride →</Link>
          </p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Trip</th><th>Role</th><th>With</th>
                  <th style={{ textAlign: "right" }}>Amount</th><th>When</th><th>Receipt</th>
                </tr>
              </thead>
              <tbody>
                {trips.map(t => (
                  <tr key={`${t.ride_id}-${t.role}`}>
                    <td>
                      <div style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                        {t.source} → {t.destination}
                      </div>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-tertiary)" }}>
                        {t.distance_km ? `${t.distance_km.toFixed(1)} km · ` : ""}
                        {t.receipt_no}
                        {t.female_only && " · 🌸 female-only"}
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${t.role === "driver" ? "badge-primary" : "badge-info"}`}>
                        {t.role === "driver" ? "🚗 Driver" : "🧍 Rider"}
                      </span>
                    </td>
                    <td style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>{t.counterparty}</td>
                    <td style={{ textAlign: "right", fontWeight: 700,
                                 color: !t.settled ? "var(--warning)"
                                        : t.role === "driver" ? "var(--success)" : "var(--text-primary)" }}>
                      {t.role === "driver" ? "+" : "−"}{taka(t.amount)}
                      {!t.settled && (
                        <div style={{ fontSize: "0.68rem", fontWeight: 600 }}>⚠️ unpaid</div>
                      )}
                    </td>
                    <td style={{ fontSize: "0.76rem", color: "var(--text-tertiary)", whiteSpace: "nowrap" }}>
                      {when(t.when)}
                    </td>
                    <td>
                      <Link href={`/dashboard/history/${t.ride_id}`} className="btn btn-ghost btn-sm">
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Feature 7: star + comment dialog */}
      {rateTarget && (
        <div className="modal-backdrop" onClick={() => !rating && setRateTarget(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 420 }}>
            <div className="modal-title">Rate {rateTarget.driver_name}</div>
            <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: 16 }}>
              {rateTarget.source} → {rateTarget.destination}
            </div>

            <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
              {[1, 2, 3, 4, 5].map(n => (
                <button
                  key={n}
                  onClick={() => setStars(n)}
                  aria-label={`${n} star${n === 1 ? "" : "s"}`}
                  style={{ background: "none", border: "none", cursor: "pointer",
                           fontSize: "1.9rem", lineHeight: 1, padding: 0,
                           opacity: n <= stars ? 1 : 0.25 }}
                >
                  ⭐
                </button>
              ))}
              <span style={{ alignSelf: "center", marginLeft: 8, color: "var(--text-secondary)",
                             fontSize: "0.85rem" }}>
                {stars} / 5
              </span>
            </div>

            <div className="input-group">
              <label className="input-label">Comment (optional)</label>
              <textarea
                className="input textarea"
                value={comment}
                onChange={e => setComment(e.target.value)}
                placeholder="How was the ride?"
                maxLength={500}
                rows={3}
              />
            </div>

            <div className="modal-actions">
              <button className="btn btn-ghost" disabled={rating} onClick={() => setRateTarget(null)}>
                Not now
              </button>
              <button className="btn btn-primary" disabled={rating} onClick={submitReview}>
                {rating ? <span className="spinner" /> : "Submit review"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

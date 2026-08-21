"use client";
import { useState, useEffect, useCallback } from "react";

import { API } from "@/lib/api";

// Feature 16: Driver Earnings Dashboard — aggregates completed rides, no new schema.

interface EarningRide {
  ride_id: string;
  source: string;
  destination: string;
  base_fare: number;
  surge_multiplier: number;
  gross: number;
  net: number;
  passengers: number;
  distance_km: number | null;
  ended_at: string | null;
  paid_out: boolean;
  week_start: string;
}

interface Week {
  week_start: string;
  rides: number;
  gross: number;
  net: number;
}

interface Summary {
  rides_completed: number;
  total_gross: number;
  total_net: number;
  platform_fee_rate: number;
  platform_fee_total: number;
  pending_payout: number;
  total_km: number;
  passengers_served: number;
  avg_per_ride: number;
  this_week: Week;
  best_week: Week | null;
  weekly: Week[];
  rides: EarningRide[];
}

const weekLabel = (iso: string) => {
  if (iso === "unknown") return "Undated";
  const d = new Date(iso);
  return d.toLocaleDateString([], { day: "numeric", month: "short" });
};

export default function EarningsPage() {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  const [paying, setPaying] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  // setState only inside promise callbacks — never synchronously in the effect body.
  const load = useCallback(() => {
    if (!token) return;
    fetch(`${API}/earnings/summary`, {
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    })
      .then(res => (res.ok ? res.json() : Promise.reject(new Error("failed"))))
      .then(setData)
      .catch(() => setError("Could not load your earnings right now."));
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const showNotice = (type: "success" | "error", text: string) => {
    setNotice({ type, text });
    setTimeout(() => setNotice(null), 4000);
  };

  const cashOut = async () => {
    setPaying(true);
    try {
      const res = await fetch(`${API}/earnings/payout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      });
      const body = await res.json();
      if (res.ok) {
        showNotice("success", body.message);
        load();
      } else {
        showNotice("error", body.detail || "Payout failed");
      }
    } catch {
      showNotice("error", "Network error — could not request a payout");
    } finally {
      setPaying(false);
    }
  };

  // Bar heights are relative to the best week in the window.
  const peak = data ? Math.max(...data.weekly.map(w => w.net), 1) : 1;

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">📊 Driver Earnings</h1>
        <p className="page-subtitle">
          What your completed rides paid, week by week, and what is waiting to be cashed out
        </p>
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

      {data && data.rides_completed === 0 && (
        <div className="glass-card" style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
          <div style={{ fontSize: "3rem", marginBottom: 16 }}>📊</div>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>No earnings yet</div>
          <div style={{ fontSize: "0.85rem" }}>Complete a ride as a driver and it will show up here</div>
        </div>
      )}

      {data && data.rides_completed > 0 && (
        <>
          <div className="stats-grid" style={{ marginBottom: 24 }}>
            <div className="glass-card stat-card">
              <div className="stat-icon" style={{ background: "var(--success-muted)" }}>💰</div>
              <div className="stat-value">৳{data.total_net.toFixed(2)}</div>
              <div className="stat-label">Total earned (after fees)</div>
            </div>
            <div className="glass-card stat-card">
              <div className="stat-icon" style={{ background: "var(--primary-muted)" }}>🚗</div>
              <div className="stat-value">{data.rides_completed}</div>
              <div className="stat-label">Rides completed</div>
            </div>
            <div className="glass-card stat-card">
              <div className="stat-icon" style={{ background: "var(--info-muted)" }}>📅</div>
              <div className="stat-value">৳{data.this_week.net.toFixed(2)}</div>
              <div className="stat-label">This week ({data.this_week.rides} rides)</div>
            </div>
            <div className="glass-card stat-card">
              <div className="stat-icon" style={{ background: "var(--accent-muted)" }}>🧾</div>
              <div className="stat-value">৳{data.avg_per_ride.toFixed(2)}</div>
              <div className="stat-label">Average per ride</div>
            </div>
          </div>

          {/* Payout */}
          <div
            className="glass-card"
            style={{
              padding: 24, marginBottom: 24, display: "flex", alignItems: "center",
              justifyContent: "space-between", gap: 16, flexWrap: "wrap",
              border: data.pending_payout > 0 ? "1px solid rgba(16,185,129,0.35)" : undefined,
            }}
          >
            <div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: 1 }}>
                Upcoming payout
              </div>
              <div style={{ fontSize: "1.9rem", fontWeight: 800, color: data.pending_payout > 0 ? "var(--success)" : "var(--text-secondary)" }}>
                ৳{data.pending_payout.toFixed(2)}
              </div>
              <div style={{ fontSize: "0.78rem", color: "var(--text-tertiary)", marginTop: 4 }}>
                Arooohi keeps {Math.round(data.platform_fee_rate * 100)}% (৳{data.platform_fee_total.toFixed(2)} so far) ·
                {" "}gross ৳{data.total_gross.toFixed(2)}
              </div>
            </div>
            <button
              className="btn btn-primary"
              onClick={cashOut}
              disabled={paying || data.pending_payout <= 0}
            >
              {paying ? <span className="spinner" /> : "Cash out to wallet"}
            </button>
          </div>

          {/* Weekly chart */}
          <div className="glass-card" style={{ padding: 24, marginBottom: 24 }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 16 }}>Weekly earnings</h3>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 14, height: 170, paddingBottom: 8 }}>
              {[...data.weekly].reverse().map(w => (
                <div key={w.week_start} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, height: "100%", justifyContent: "flex-end" }}>
                  <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--text-secondary)" }}>
                    ৳{w.net.toFixed(0)}
                  </div>
                  <div
                    title={`${w.rides} rides · net ৳${w.net.toFixed(2)}`}
                    style={{
                      width: "100%", maxWidth: 54,
                      height: `${Math.max((w.net / peak) * 100, 3)}%`,
                      background: w.week_start === data.this_week.week_start
                        ? "linear-gradient(180deg, var(--primary), rgba(99,102,241,0.35))"
                        : "linear-gradient(180deg, rgba(148,163,184,0.55), rgba(148,163,184,0.16))",
                      borderRadius: "var(--radius-md) var(--radius-md) 4px 4px",
                      transition: "height 0.5s ease",
                    }}
                  />
                  <div style={{ fontSize: "0.7rem", color: "var(--text-tertiary)" }}>{weekLabel(w.week_start)}</div>
                </div>
              ))}
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", marginTop: 8 }}>
              Week beginning Monday · highlighted bar is the current week
              {data.best_week && ` · best week ৳${data.best_week.net.toFixed(2)}`}
            </div>
          </div>

          {/* Per-ride breakdown */}
          <div className="glass-card" style={{ padding: 20 }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 4 }}>Ride breakdown</h3>
            <div style={{ fontSize: "0.78rem", color: "var(--text-tertiary)", marginBottom: 12 }}>
              Gross is base fare × surge — the same figure the passengers split.
            </div>
            {data.rides.map(r => (
              <div
                key={r.ride_id}
                style={{
                  display: "flex", alignItems: "center", gap: 12, padding: "12px 0",
                  borderBottom: "1px solid rgba(100,120,200,0.06)", flexWrap: "wrap",
                }}
              >
                <div style={{ flex: 1, minWidth: 180 }}>
                  <div style={{ fontWeight: 600, fontSize: "0.88rem" }}>
                    {r.source} ➜ {r.destination}
                  </div>
                  <div style={{ fontSize: "0.74rem", color: "var(--text-tertiary)" }}>
                    {r.ended_at ? new Date(r.ended_at).toLocaleDateString([], { day: "numeric", month: "short" }) : "—"}
                    {" · "}{r.passengers} passenger{r.passengers === 1 ? "" : "s"}
                    {r.distance_km ? ` · ${r.distance_km} km` : ""}
                  </div>
                </div>
                {r.surge_multiplier > 1 && (
                  <span className="badge badge-danger" style={{ fontSize: "0.7rem" }}>⚡ ×{r.surge_multiplier}</span>
                )}
                <span className={`badge ${r.paid_out ? "badge-success" : "badge-warning"}`} style={{ fontSize: "0.7rem" }}>
                  {r.paid_out ? "Paid out" : "Pending"}
                </span>
                <div style={{ textAlign: "right", minWidth: 90 }}>
                  <div style={{ fontWeight: 700, color: "var(--success)" }}>৳{r.net.toFixed(2)}</div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-tertiary)" }}>of ৳{r.gross.toFixed(2)}</div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}

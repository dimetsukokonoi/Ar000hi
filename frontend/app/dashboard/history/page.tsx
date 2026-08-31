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

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token]
  );

  const fetchAll = useCallback(async (role: Filter) => {
    const [t, s] = await Promise.all([
      fetch(`${API}/history?role=${role}&limit=100`, { headers }).then(r => r.json()),
      fetch(`${API}/history/summary`, { headers }).then(r => r.json()),
    ]);
    return { t: (Array.isArray(t) ? t : []) as Trip[], s: s as Summary };
  }, [headers]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchAll(filter)
      .then(({ t, s }) => {
        if (cancelled) return;
        setTrips(t);
        setSummary(s);
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) { setError("Could not load your ride history."); setLoading(false); }
      });
    return () => { cancelled = true; };
  }, [token, filter, fetchAll]);

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
    </div>
  );
}

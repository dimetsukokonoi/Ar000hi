"use client";
import { useState, useEffect } from "react";

const API = "http://localhost:8000/api";

// Ornab: Eco/Footprint Tracker (Feature 20) — CO2 saved by carpooling vs solo rides
export default function EcoTrackerPage() {
  const [stats, setStats] = useState<any>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  useEffect(() => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    fetch(`${API}/eco/stats`, { headers })
      .then(res => res.ok ? res.json() : null)
      .then(setStats)
      .catch(err => console.error("Failed to load eco stats:", err));
  }, [token]);

  // Progress ring via SVG
  const pct = stats ? Math.min(100, (stats.trees_equivalent / 5) * 100) : 0;
  const R = 52;
  const CIRC = 2 * Math.PI * R;

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">🌱 Eco/Footprint Tracker</h1>
        <p className="page-subtitle">See how much CO₂ you saved by choosing to carpool instead of driving solo</p>
      </div>

      {!stats ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 48 }}><span className="spinner spinner-lg" /></div>
      ) : stats.trips === 0 ? (
        <div className="glass-card" style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
          <div style={{ fontSize: "3rem", marginBottom: 16 }}>🌱</div>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>No eco data yet</div>
          <div style={{ fontSize: "0.85rem" }}>Complete a shared ride and your footprint savings will appear here</div>
        </div>
      ) : (
        <>
          <div className="stats-grid" style={{ marginBottom: 32 }}>
            <div className="glass-card stat-card">
              <div className="stat-icon" style={{ background: "var(--primary-muted)" }}>🚗</div>
              <div className="stat-value">{stats.trips}</div>
              <div className="stat-label">Shared trips completed</div>
            </div>
            <div className="glass-card stat-card">
              <div className="stat-icon" style={{ background: "var(--info-muted)" }}>🛣️</div>
              <div className="stat-value">{stats.total_km} <span style={{ fontSize: "0.8rem", fontWeight: 500 }}>km</span></div>
              <div className="stat-label">Total distance carpooled</div>
            </div>
            <div className="glass-card stat-card">
              <div className="stat-icon" style={{ background: "var(--success-muted)" }}>💨</div>
              <div className="stat-value">{stats.total_saved_kg} <span style={{ fontSize: "0.8rem", fontWeight: 500 }}>kg</span></div>
              <div className="stat-label">CO₂ saved vs solo driving</div>
            </div>
            <div className="glass-card stat-card">
              <div className="stat-icon" style={{ background: "var(--accent-muted)" }}>⛽</div>
              <div className="stat-value">{stats.fuel_saved_l} <span style={{ fontSize: "0.8rem", fontWeight: 500 }}>L</span></div>
              <div className="stat-label">Fuel saved (approx.)</div>
            </div>
          </div>

          <div className="glass-card" style={{ padding: 32, display: "flex", alignItems: "center", gap: 32, flexWrap: "wrap" }}>
            <div style={{ position: "relative", width: 140, height: 140 }}>
              <svg width="140" height="140" viewBox="0 0 140 140">
                <circle cx="70" cy="70" r={R} fill="none" stroke="var(--surface-border)" strokeWidth="10" />
                <circle
                  cx="70" cy="70" r={R} fill="none"
                  stroke="var(--primary)" strokeWidth="10" strokeLinecap="round"
                  strokeDasharray={CIRC}
                  strokeDashoffset={CIRC * (1 - pct / 100)}
                  transform="rotate(-90 70 70)"
                  style={{ transition: "stroke-dashoffset 0.6s ease" }}
                />
              </svg>
              <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
                <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--primary)" }}>{stats.trees_equivalent}</div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-tertiary)" }}>trees</div>
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 220 }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 8 }}>🌳 Tree Equivalent</h3>
              <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", lineHeight: 1.7 }}>
                Your carpooling has saved enough CO₂ to equal <strong style={{ color: "var(--primary)" }}>{stats.trees_equivalent} trees</strong> absorbing carbon for a year (1 tree ≈ 21 kg CO₂). Keep sharing rides to grow your forest!
              </p>
            </div>
          </div>

          {stats.rides.length > 0 && (
            <div className="glass-card" style={{ padding: 20, marginTop: 24 }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 12 }}>Trip Breakdown</h3>
              {stats.rides.map(r => (
                <div key={r.ride_id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid rgba(100,120,200,0.06)", fontSize: "0.85rem" }}>
                  <span style={{ color: "var(--text-secondary)" }}>{r.distance_km} km · {r.occupancy} people</span>
                  <span style={{ color: "var(--success)", fontWeight: 700 }}>saved {r.saved_kg} kg CO₂</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}

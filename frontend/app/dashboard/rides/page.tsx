"use client";
import { useState, useEffect } from "react";
import Link from "next/link";

import { API } from "@/lib/api";
const HOTSPOTS = ["Gate 1", "Gate 2", "Gate 3", "Library", "Cafeteria", "UB Building", "Residential", "Mohakhali", "Banani", "Gulshan"];

interface RideInfo {
  id: string;
  driver_id: string;
  driver_name: string;
  source: string;
  destination: string;
  status: string;
  distance_km: number | null;
  base_fare: number;
  surge_multiplier: number;
  total_seats: number;
  scheduled_at?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  created_at?: string | null;
}

interface SurgeInfo {
  hour: number;
  demand: number;
  active_rides: number;
  multiplier: number;
  label: string;
  message: string;
}

interface SurgeHour {
  hour: number;
  demand: number;
  multiplier: number;
  label: string;
  is_current: boolean;
}

interface SplitInfo {
  ride_id: string;
  source: string;
  destination: string;
  base_fare: number;
  surge_multiplier: number;
  total: number;
  total_seats: number;
  passenger_count: number;
  per_seat: number | null;
  breakdown: { passenger: string; seats: number; share: number }[];
}

interface MeInfo {
  id: string;
}

const BADGES: Record<string, string> = {
  "Peak": "badge-danger",
  "High": "badge-warning",
  "Elevated": "badge-info",
  "Normal": "badge-success",
};

// Ornab: Rides page — surge indicator + hourly surge strip + ride create/join
// + seat-aware cost splitter + participant-gated chat entry.
export default function RidesPage() {
  const [surge, setSurge] = useState<SurgeInfo | null>(null);
  const [schedule, setSchedule] = useState<SurgeHour[]>([]);
  const [rides, setRides] = useState<{ mine: RideInfo[]; available: RideInfo[] }>({ mine: [], available: [] });
  const [form, setForm] = useState({ source: "", destination: "", base_fare: "", total_seats: "4" });
  const [split, setSplit] = useState<Record<string, SplitInfo>>({});
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [me] = useState<MeInfo | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      const raw = localStorage.getItem("user");
      return raw ? (JSON.parse(raw) as MeInfo) : null;
    } catch {
      return null;
    }
  });

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const showNotice = (type: "success" | "error", text: string) => {
    setNotice({ type, text });
    setTimeout(() => setNotice(null), 5000);
  };

  useEffect(() => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    Promise.all([
      fetch(`${API}/surge/current`, { headers }).then(res => res.json()).catch(() => null),
      fetch(`${API}/surge/schedule`, { headers }).then(res => res.json()).then(d => (d?.schedule ?? [])).catch(() => []),
      fetch(`${API}/rides`, { headers }).then(res => res.json()).catch(() => ({ mine: [], available: [] })),
    ]).then(([s, sc, r]) => { setSurge(s); setSchedule(sc); setRides(r); });
  }, [token]);

  const createRide = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    setLoading(true);
    try {
      const res = await fetch(`${API}/rides`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          source: form.source,
          destination: form.destination,
          base_fare: Number(form.base_fare),
          total_seats: Number(form.total_seats),
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setForm({ source: "", destination: "", base_fare: "", total_seats: "4" });
        showNotice("success", data.message || "Ride created");
        reload();
      } else {
        showNotice("error", data.detail || "Failed to create ride");
      }
    } catch (err) {
      showNotice("error", "Network error — could not create ride");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const joinRide = async (rideId: string) => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    try {
      const res = await fetch(`${API}/rides/${rideId}/join`, { method: "POST", headers, body: JSON.stringify({ seats: 1 }) });
      const data = await res.json();
      showNotice(res.ok ? "success" : "error", res.ok ? data.message : (data.detail || "Failed to join"));
      reload();
    } catch (err) {
      showNotice("error", "Network error — could not join ride");
      console.error(err);
    }
  };

  const reload = async () => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    const r = await fetch(`${API}/rides`, { headers }).then(res => res.json()).catch(() => ({ mine: [], available: [] }));
    const s = await fetch(`${API}/surge/current`, { headers }).then(res => res.json()).catch(() => null);
    setRides(r);
    setSurge(s);
  };

  const loadSplit = async (rideId: string) => {
    if (split[rideId]) { setSplit({}); return; }
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    try {
      const res = await fetch(`${API}/rides/${rideId}/split`, { headers });
      const data = await res.json();
      if (!res.ok) { showNotice("error", data.detail || "Could not load fare split"); return; }
      setSplit({ [rideId]: data });
    } catch (err) {
      showNotice("error", "Network error — could not load fare split");
      console.error(err);
    }
  };

  const surgeBadge = surge ? BADGES[surge.label] || "badge-success" : "badge-success";

  const upcomingPeaks = schedule
    .filter(h => h.hour > (surge?.hour ?? -1))
    .slice(0, 6)
    .filter(h => h.multiplier >= 1.3);

  const renderRideCard = (ride: RideInfo, mine: boolean) => {
    const s = split[ride.id];
    const isParticipant = mine || (me && ride.driver_id === me.id);
    // Chat is only for the driver or an accepted/participating rider.
    const chatOpen = isParticipant && (ride.status === "active" || ride.status === "scheduled");
    return (
      <div key={ride.id} className="glass-card" style={{ padding: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
          <div>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>
              {ride.source} → {ride.destination}
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
              Driver: {ride.driver_name} · {ride.status} · est. {ride.distance_km || "—"} km
              {ride.total_seats ? ` · ${ride.total_seats} seats` : ""}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
            <span className={`badge ${ride.status === "completed" ? "badge-success" : ride.status === "active" ? "badge-info" : "badge-warning"}`}>
              {ride.status}
            </span>
            {ride.surge_multiplier > 1 && (
              <span className="badge badge-danger">⚡ Surge ×{ride.surge_multiplier}</span>
            )}
          </div>
        </div>

        <div style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: 12 }}>
          Fare: <strong style={{ color: "var(--text-primary)" }}>৳{ride.base_fare}</strong>
          {ride.surge_multiplier > 1 && (
            <span style={{ color: "var(--warning)", marginLeft: 8 }}>
              × {ride.surge_multiplier} = ৳{(ride.base_fare * ride.surge_multiplier).toFixed(2)}
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {!mine && ride.status === "scheduled" && (
            <button className="btn btn-sm btn-primary" onClick={() => joinRide(ride.id)}>🚕 Request Seat</button>
          )}
          {(isParticipant && (ride.status === "active" || ride.status === "completed")) && (
            <button className="btn btn-sm btn-secondary" onClick={() => loadSplit(ride.id)}>
              💸 Cost Splitter
            </button>
          )}
          {chatOpen && (
            <Link href={`/dashboard/chat/${ride.id}`} className="btn btn-sm btn-secondary">💬 Ride Chat</Link>
          )}
        </div>

        {s && (
          <div style={{ marginTop: 16, padding: 16, background: "var(--surface)", borderRadius: "var(--radius-md)" }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>💸 Fare Breakdown</div>
            <div style={{ fontSize: "0.85rem", display: "grid", gap: 4, color: "var(--text-secondary)" }}>
              <div>Base fare: ৳{s.base_fare} × surge {s.surge_multiplier}</div>
              <div>Total: <strong style={{ color: "var(--text-primary)" }}>৳{s.total}</strong> · {s.passenger_count} passenger(s) · {s.total_seats} seat(s)</div>
              <div style={{ color: "var(--primary)", fontWeight: 700, fontSize: "1rem", marginTop: 4 }}>
                Per seat: ৳{s.per_seat ?? "—"}
              </div>
            </div>
            {s.breakdown.length > 0 && (
              <div style={{ marginTop: 8, fontSize: "0.8rem", color: "var(--text-tertiary)" }}>
                {s.breakdown.map((b, i) => (
                  <div key={i}>• {b.passenger}{b.seats > 1 ? ` (${b.seats} seats)` : ""}: ৳{b.share}</div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">🚗 Rides</h1>
        <p className="page-subtitle">Create or join rides · live surge pricing · split fares</p>
      </div>

      {notice && (
        <div style={{
          padding: "12px 16px",
          borderRadius: "var(--radius-md)",
          fontSize: "0.85rem",
          marginBottom: 20,
          background: notice.type === "success" ? "var(--success-muted)" : "var(--danger-muted)",
          color: notice.type === "success" ? "var(--success)" : "var(--danger)",
        }}>
          {notice.text}
        </div>
      )}

      {/* Peak Hour Surge Indicator (Ornab, Feature 13) */}
      {surge && (
        <div className="glass-card" style={{ padding: 20, marginBottom: 24, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: "1.5rem" }}>⚡</span>
            <div>
              <div style={{ fontWeight: 700 }}>Peak Hour Surge</div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{surge.message}</div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className={`badge ${surgeBadge}`}>{surge.label}</span>
            <span style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--warning)" }}>×{surge.multiplier}</span>
          </div>
        </div>
      )}

      {/* Upcoming peak strip (Feature 13 improvement — plan rides better) */}
      {upcomingPeaks.length > 0 && (
        <div className="glass-card" style={{ padding: 16, marginBottom: 24 }}>
          <div style={{ fontWeight: 600, fontSize: "0.9rem", marginBottom: 10 }}>⏰ Upcoming peak windows</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {upcomingPeaks.map(h => (
              <span key={h.hour} className={`badge ${h.multiplier >= 1.5 ? "badge-danger" : "badge-warning"}`} style={{ textTransform: "none" }}>
                {h.hour.toString().padStart(2, "0")}:00 — ×{h.multiplier} {h.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Create ride (driver side) */}
      <div className="glass-card" style={{ padding: 24, marginBottom: 32 }}>
        <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 16 }}>➕ Offer a Ride</h3>
        <form onSubmit={createRide} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 140px 120px auto", gap: 16, alignItems: "end" }}>
          <div className="input-group">
            <label className="input-label">From (hotspot)</label>
            <select className="input select" required value={form.source} onChange={e => setForm({ ...form, source: e.target.value })}>
              <option value="">Select pickup</option>
              {HOTSPOTS.map(h => <option key={h} value={h}>{h}</option>)}
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">To (hotspot)</label>
            <select className="input select" required value={form.destination} onChange={e => setForm({ ...form, destination: e.target.value })}>
              <option value="">Select drop-off</option>
              {HOTSPOTS.map(h => <option key={h} value={h}>{h}</option>)}
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">Base fare (৳)</label>
            <input className="input" type="number" min="10" step="5" required placeholder="e.g. 100" value={form.base_fare} onChange={e => setForm({ ...form, base_fare: e.target.value })} />
          </div>
          <div className="input-group">
            <label className="input-label">Seats</label>
            <input className="input" type="number" min="1" max="10" required value={form.total_seats} onChange={e => setForm({ ...form, total_seats: e.target.value })} />
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading}>{loading ? "Creating..." : "Create Ride"}</button>
        </form>
      </div>

      {/* My rides */}
      <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 12 }}>My Rides</h3>
      <div style={{ display: "grid", gap: 12, marginBottom: 32 }}>
        {rides.mine.length === 0 && <div style={{ color: "var(--text-tertiary)", fontSize: "0.9rem", padding: 8 }}>No rides yet. Offer one above, or join an available ride below.</div>}
        {rides.mine.map(r => renderRideCard(r, true))}
      </div>

      {/* Available rides */}
      <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 12 }}>Available Rides</h3>
      <div style={{ display: "grid", gap: 12 }}>
        {rides.available.length === 0 && <div style={{ color: "var(--text-tertiary)", fontSize: "0.9rem", padding: 8 }}>No rides available right now.</div>}
        {rides.available.map(r => renderRideCard(r, false))}
      </div>
    </>
  );
}

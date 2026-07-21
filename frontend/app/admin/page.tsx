"use client";
import { useEffect, useState } from "react";

const API = "http://localhost:8000/api";

export default function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [sosAlerts, setSosAlerts] = useState<any[]>([]);
  const [drivers, setDrivers] = useState<any[]>([]);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/complaints/stats`, { headers }).then(r => r.json()).then(setStats).catch(() => {});
    fetch(`${API}/sos/alerts`, { headers }).then(r => r.json()).then(data => setSosAlerts(Array.isArray(data) ? data.slice(0, 5) : [])).catch(() => {});
    fetch(`${API}/drivers/pending`, { headers }).then(r => r.json()).then(data => setDrivers(Array.isArray(data) ? data.filter((d: any) => d.verification_status === "pending") : [])).catch(() => {});
  }, [token]);

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">📊 Admin Dashboard</h1>
        <p className="page-subtitle">System overview and quick actions</p>
      </div>

      {/* Stats Cards */}
      <div className="stats-grid">
        <div className="glass-card stat-card">
          <div className="stat-icon" style={{ background: "var(--warning-muted)", color: "var(--warning)" }}>📋</div>
          <div className="stat-value">{stats?.total || 0}</div>
          <div className="stat-label">Total Complaints</div>
        </div>
        <div className="glass-card stat-card">
          <div className="stat-icon" style={{ background: "var(--danger-muted)", color: "var(--danger)" }}>🔴</div>
          <div className="stat-value">{stats?.open || 0}</div>
          <div className="stat-label">Open Complaints</div>
        </div>
        <div className="glass-card stat-card">
          <div className="stat-icon" style={{ background: "var(--info-muted)", color: "var(--info)" }}>🔍</div>
          <div className="stat-value">{stats?.under_review || 0}</div>
          <div className="stat-label">Under Review</div>
        </div>
        <div className="glass-card stat-card">
          <div className="stat-icon" style={{ background: "var(--success-muted)", color: "var(--success)" }}>✅</div>
          <div className="stat-value">{stats?.resolved || 0}</div>
          <div className="stat-label">Resolved</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {/* Recent SOS Alerts */}
        <div className="glass-card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
            🆘 Recent SOS Alerts
            {sosAlerts.some(a => a.status === "active") && <span className="badge badge-danger" style={{ fontSize: "0.65rem" }}>ACTIVE</span>}
          </h3>
          {sosAlerts.length === 0 ? (
            <div style={{ color: "var(--text-tertiary)", fontSize: "0.85rem", padding: 16, textAlign: "center" }}>No SOS alerts</div>
          ) : (
            sosAlerts.map(a => (
              <div key={a.id} style={{ padding: "12px 0", borderBottom: "1px solid var(--surface-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 500, fontSize: "0.85rem" }}>{a.user_name}</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-tertiary)" }}>
                    {new Date(a.created_at).toLocaleString()} • 📍 {a.lat.toFixed(4)}, {a.lng.toFixed(4)}
                  </div>
                </div>
                <span className={`badge ${a.status === "active" ? "badge-danger" : "badge-success"}`}>{a.status}</span>
              </div>
            ))
          )}
        </div>

        {/* Pending Driver Verifications */}
        <div className="glass-card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 16 }}>
            📄 Pending Driver Verifications
            {drivers.length > 0 && <span className="badge badge-warning" style={{ marginLeft: 8, fontSize: "0.65rem" }}>{drivers.length}</span>}
          </h3>
          {drivers.length === 0 ? (
            <div style={{ color: "var(--text-tertiary)", fontSize: "0.85rem", padding: 16, textAlign: "center" }}>No pending verifications</div>
          ) : (
            drivers.map(d => (
              <div key={d.id} style={{ padding: "12px 0", borderBottom: "1px solid var(--surface-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 500, fontSize: "0.85rem" }}>{d.name}</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-tertiary)" }}>{d.email} • {d.vehicle_type} — {d.vehicle_model}</div>
                </div>
                <span className="badge badge-warning">Pending</span>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}

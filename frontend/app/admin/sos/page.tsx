"use client";
import { useEffect, useState, useCallback } from "react";

const API = "http://localhost:8000/api";

interface SosAlert {
  id: string;
  user_name: string;
  user_email: string;
  user_phone: string;
  status: string;
  lat: number;
  lng: number;
  created_at: string;
  contacts_notified?: { name: string; phone: string }[];
}

export default function AdminSOSPage() {
  const [alerts, setAlerts] = useState<SosAlert[]>([]);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchAlerts = useCallback(() => {
    const h = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    fetch(`${API}/sos/alerts`, { headers: h }).then(r => r.json()).then(data => setAlerts(Array.isArray(data) ? data : [])).catch(() => {});
  }, [token]);

  useEffect(() => { fetchAlerts(); }, [fetchAlerts]);

  const resolveAlert = async (id: string, status: string) => {
    await fetch(`${API}/sos/${id}/resolve`, { method: "PATCH", headers, body: JSON.stringify({ status }) });
    fetchAlerts();
  };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">🆘 SOS Alerts</h1>
        <p className="page-subtitle">Monitor and manage emergency alerts from students</p>
      </div>

      {alerts.length === 0 ? (
        <div style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
          <div style={{ fontSize: "3rem", marginBottom: 16 }}>✅</div>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)" }}>No SOS alerts</div>
          <div style={{ fontSize: "0.85rem" }}>All clear — no emergencies reported</div>
        </div>
      ) : (
        alerts.map(a => (
          <div key={a.id} className="glass-card" style={{ padding: 24, marginBottom: 16, borderLeftWidth: 3, borderLeftStyle: "solid", borderLeftColor: a.status === "active" ? "var(--danger)" : "var(--success)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: "1.05rem" }}>{a.user_name}</div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-tertiary)" }}>
                  {a.user_email} • 📞 {a.user_phone}
                </div>
              </div>
              <span className={`badge ${a.status === "active" ? "badge-danger" : "badge-success"}`}>
                {a.status === "active" ? "🔴 ACTIVE" : `✅ ${a.status}`}
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
              <div style={{ padding: 12, background: "var(--surface)", borderRadius: "var(--radius-md)", fontSize: "0.85rem" }}>
                <div style={{ color: "var(--text-tertiary)", fontSize: "0.7rem", marginBottom: 4 }}>📍 LOCATION</div>
                {a.lat.toFixed(5)}, {a.lng.toFixed(5)}
              </div>
              <div style={{ padding: 12, background: "var(--surface)", borderRadius: "var(--radius-md)", fontSize: "0.85rem" }}>
                <div style={{ color: "var(--text-tertiary)", fontSize: "0.7rem", marginBottom: 4 }}>🕐 TIME</div>
                {new Date(a.created_at).toLocaleString()}
              </div>
            </div>

            {/* Contacts notified */}
            {(a.contacts_notified?.length ?? 0) > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 6 }}>Contacts Notified:</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {a.contacts_notified?.map((c, i) => (
                    <span key={i} className="badge badge-info" style={{ textTransform: "none" }}>
                      {c.name} — {c.phone}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {a.status === "active" && (
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-sm btn-primary" onClick={() => resolveAlert(a.id, "resolved")}>✅ Mark Resolved</button>
                <button className="btn btn-sm btn-ghost" onClick={() => resolveAlert(a.id, "false_alarm")}>False Alarm</button>
              </div>
            )}
          </div>
        ))
      )}
    </>
  );
}

"use client";
import { useEffect, useState, useCallback } from "react";

const API = "http://localhost:8000/api";

interface DriverApp {
  id: string;
  name: string;
  email: string;
  phone: string;
  gender: string;
  verification_status: string;
  vehicle_type: string;
  vehicle_model: string;
  vehicle_plate: string;
  nid_document_url: string;
  license_document_url: string;
  vehicle_registration_url: string;
  admin_notes?: string;
}

export default function AdminDriversPage() {
  const [drivers, setDrivers] = useState<DriverApp[]>([]);
  const [filter, setFilter] = useState("all");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchDrivers = useCallback(() => {
    const h = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    fetch(`${API}/drivers/pending`, { headers: h }).then(r => r.json()).then(data => setDrivers(Array.isArray(data) ? data : [])).catch(() => {});
  }, [token]);

  useEffect(() => { fetchDrivers(); }, [fetchDrivers]);

  const reviewDriver = async (profileId: string, status: string, notes: string = "") => {
    await fetch(`${API}/drivers/${profileId}/review`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ status, admin_notes: notes }),
    });
    fetchDrivers();
  };

  const filtered = filter === "all" ? drivers : drivers.filter(d => d.verification_status === filter);

  const statusBadge: Record<string, string> = { pending: "badge-warning", approved: "badge-success", rejected: "badge-danger" };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">📄 Driver Verification</h1>
        <p className="page-subtitle">Review and approve driver document submissions</p>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        {["all", "pending", "approved", "rejected"].map(f => (
          <button key={f} className={`btn btn-sm ${filter === f ? "btn-primary" : "btn-ghost"}`} onClick={() => setFilter(f)}>
            {f.charAt(0).toUpperCase() + f.slice(1)} ({f === "all" ? drivers.length : drivers.filter(d => d.verification_status === f).length})
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
          <div style={{ fontSize: "3rem", marginBottom: 16 }}>📄</div>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)" }}>No driver applications in this category</div>
        </div>
      ) : (
        filtered.map(d => (
          <div key={d.id} className="glass-card" style={{ padding: 24, marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
              <div>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 600 }}>{d.name}</h3>
                <div style={{ fontSize: "0.8rem", color: "var(--text-tertiary)", marginTop: 4 }}>
                  {d.email} • 📞 {d.phone} • {d.gender}
                </div>
              </div>
              <span className={`badge ${statusBadge[d.verification_status]}`}>{d.verification_status}</span>
            </div>

            {/* Vehicle Info */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 16 }}>
              <div style={{ padding: 12, background: "var(--surface)", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: "0.7rem", color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: 4 }}>Vehicle Type</div>
                <div style={{ fontWeight: 600 }}>{d.vehicle_type}</div>
              </div>
              <div style={{ padding: 12, background: "var(--surface)", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: "0.7rem", color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: 4 }}>Model</div>
                <div style={{ fontWeight: 600 }}>{d.vehicle_model}</div>
              </div>
              <div style={{ padding: 12, background: "var(--surface)", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: "0.7rem", color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: 4 }}>Plate</div>
                <div style={{ fontWeight: 600 }}>{d.vehicle_plate}</div>
              </div>
            </div>

            {/* Documents */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 8 }}>Uploaded Documents:</div>
              <div style={{ display: "flex", gap: 12 }}>
                {[
                  { label: "🪪 NID", url: d.nid_document_url },
                  { label: "📄 License", url: d.license_document_url },
                  { label: "🚗 Vehicle Reg", url: d.vehicle_registration_url },
                ].map(doc => (
                  <a
                    key={doc.label}
                    href={`http://localhost:8000${doc.url}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-sm btn-secondary"
                  >
                    {doc.label}
                  </a>
                ))}
              </div>
            </div>

            {/* Actions */}
            {d.verification_status === "pending" && (
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-sm btn-primary" onClick={() => reviewDriver(d.id, "approved", "Documents verified. Welcome aboard!")}>
                  ✅ Approve
                </button>
                <button className="btn btn-sm btn-danger" onClick={() => reviewDriver(d.id, "rejected", "Documents unclear. Please resubmit.")}>
                  ❌ Reject
                </button>
              </div>
            )}

            {d.admin_notes && (
              <div style={{ marginTop: 12, padding: 12, background: "var(--surface)", borderRadius: "var(--radius-md)", fontSize: "0.8rem" }}>
                <strong>Admin Notes:</strong> {d.admin_notes}
              </div>
            )}
          </div>
        ))
      )}
    </>
  );
}

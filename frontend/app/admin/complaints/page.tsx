"use client";
import { useEffect, useState, useCallback } from "react";

const API = "http://localhost:8000/api";

interface Complaint {
  id: string;
  category: string;
  subject: string;
  status: string;
  reporter_name: string;
  reporter_email: string;
  created_at: string;
  description: string;
  admin_notes?: string;
}

export default function AdminComplaintsPage() {
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [adminNotes, setAdminNotes] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchComplaints = useCallback(() => {
    const h = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    fetch(`${API}/complaints/`, { headers: h }).then(r => r.json()).then(data => setComplaints(Array.isArray(data) ? data : [])).catch(() => {});
  }, [token]);

  useEffect(() => { fetchComplaints(); }, [fetchComplaints]);

  const updateComplaint = async (id: string, status: string) => {
    await fetch(`${API}/complaints/${id}`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ status, admin_notes: adminNotes }),
    });
    setSelectedId(null);
    setAdminNotes("");
    fetchComplaints();
  };

  const filtered = filter === "all" ? complaints : complaints.filter(c => c.status === filter);

  const statusBadge: Record<string, string> = { open: "badge-warning", under_review: "badge-info", resolved: "badge-success", dismissed: "badge-accent" };
  const categoryIcon: Record<string, string> = { safety: "🛡️", misconduct: "⚠️", vehicle: "🚗", payment: "💳", other: "📌" };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">🛡️ Complaint Panel</h1>
        <p className="page-subtitle">Review and manage student complaints</p>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap" }}>
        {["all", "open", "under_review", "resolved", "dismissed"].map(f => (
          <button key={f} className={`btn btn-sm ${filter === f ? "btn-primary" : "btn-ghost"}`} onClick={() => setFilter(f)}>
            {f === "all" ? "All" : f.replace("_", " ")} ({f === "all" ? complaints.length : complaints.filter(c => c.status === f).length})
          </button>
        ))}
      </div>

      {/* Complaints */}
      {filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
          <div style={{ fontSize: "3rem", marginBottom: 16 }}>📭</div>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)" }}>No complaints in this category</div>
        </div>
      ) : (
        filtered.map(c => (
          <div key={c.id} className="glass-card complaint-card">
            <div className="complaint-header">
              <div style={{ flex: 1 }}>
                <span style={{ marginRight: 8 }}>{categoryIcon[c.category] || "📌"}</span>
                <span className="complaint-subject">{c.subject}</span>
              </div>
              <span className={`badge ${statusBadge[c.status]}`}>{c.status.replace("_", " ")}</span>
            </div>
            <div className="complaint-meta">
              By <strong>{c.reporter_name}</strong> ({c.reporter_email}) • {c.category} • {new Date(c.created_at).toLocaleString()}
            </div>
            <div className="complaint-body">{c.description}</div>

            {c.admin_notes && (
              <div style={{ marginTop: 12, padding: 12, background: "var(--surface)", borderRadius: "var(--radius-md)", fontSize: "0.8rem" }}>
                <strong>Admin Notes:</strong> {c.admin_notes}
              </div>
            )}

            {/* Action buttons */}
            {selectedId === c.id ? (
              <div style={{ marginTop: 16, padding: 16, background: "var(--surface)", borderRadius: "var(--radius-md)" }}>
                <div className="input-group" style={{ marginBottom: 12 }}>
                  <label className="input-label">Admin Notes</label>
                  <textarea className="input textarea" placeholder="Add resolution notes..." value={adminNotes} onChange={e => setAdminNotes(e.target.value)} style={{ minHeight: 60 }} />
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button className="btn btn-sm btn-secondary" onClick={() => updateComplaint(c.id, "under_review")}>🔍 Mark Under Review</button>
                  <button className="btn btn-sm btn-primary" onClick={() => updateComplaint(c.id, "resolved")}>✅ Resolve</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => updateComplaint(c.id, "dismissed")}>Dismiss</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => setSelectedId(null)}>Cancel</button>
                </div>
              </div>
            ) : (
              <div style={{ marginTop: 12 }}>
                <button className="btn btn-sm btn-secondary" onClick={() => { setSelectedId(c.id); setAdminNotes(c.admin_notes || ""); }}>
                  ⚙️ Take Action
                </button>
              </div>
            )}
          </div>
        ))
      )}
    </>
  );
}

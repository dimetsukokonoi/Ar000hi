"use client";
import { useState, useEffect, useCallback } from "react";

import { API } from "@/lib/api";

interface Complaint {
  id: string;
  category: string;
  subject: string;
  status: string;
  created_at: string;
  description: string;
  admin_notes?: string;
}

export default function ComplaintsPage() {
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ category: "misconduct", subject: "", description: "" });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchComplaints = useCallback(() => {
    if (!token) return;
    const h = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    fetch(`${API}/complaints/`, { headers: h }).then(r => r.json()).then(setComplaints).catch(() => {});
  }, [token]);

  useEffect(() => { fetchComplaints(); }, [fetchComplaints]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch(`${API}/complaints/`, { method: "POST", headers, body: JSON.stringify(form) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      setMessage("Complaint filed successfully!");
      setForm({ category: "misconduct", subject: "", description: "" });
      setShowForm(false);
      fetchComplaints();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const statusBadge: Record<string, string> = {
    open: "badge-warning",
    under_review: "badge-info",
    resolved: "badge-success",
    dismissed: "badge-accent",
  };

  const categoryIcon: Record<string, string> = {
    safety: "🛡️",
    misconduct: "⚠️",
    vehicle: "🚗",
    payment: "💳",
    other: "📌",
  };

  return (
    <>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="page-title">📋 My Complaints</h1>
          <p className="page-subtitle">Report misconduct or safety issues for review</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "✕ Cancel" : "+ File Complaint"}
        </button>
      </div>

      {message && (
        <div style={{ padding: "12px 16px", background: message.includes("success") ? "var(--success-muted)" : "var(--danger-muted)", borderRadius: "var(--radius-md)", color: message.includes("success") ? "var(--success)" : "var(--danger)", fontSize: "0.85rem", marginBottom: 20 }}>
          {message}
        </div>
      )}

      {/* New Complaint Form */}
      {showForm && (
        <div className="glass-card" style={{ padding: 24, marginBottom: 24, animation: "fadeInUp 0.3s ease" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 16 }}>File a New Complaint</h3>
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="input-group">
              <label className="input-label">Category</label>
              <select className="input select" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                <option value="safety">🛡️ Safety</option>
                <option value="misconduct">⚠️ Misconduct</option>
                <option value="vehicle">🚗 Vehicle Issue</option>
                <option value="payment">💳 Payment</option>
                <option value="other">📌 Other</option>
              </select>
            </div>
            <div className="input-group">
              <label className="input-label">Subject</label>
              <input className="input" placeholder="Brief description of the issue" required value={form.subject} onChange={e => setForm({ ...form, subject: e.target.value })} />
            </div>
            <div className="input-group">
              <label className="input-label">Details</label>
              <textarea className="input textarea" placeholder="Describe the incident in detail..." required value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
            </div>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? <span className="spinner" /> : "Submit Complaint"}
            </button>
          </form>
        </div>
      )}

      {/* Complaints List */}
      {complaints.length === 0 ? (
        <div style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
          <div style={{ fontSize: "3rem", marginBottom: 16 }}>📭</div>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>No complaints yet</div>
          <div style={{ fontSize: "0.85rem" }}>File a complaint if you encounter any issues</div>
        </div>
      ) : (
        complaints.map(c => (
          <div key={c.id} className="glass-card complaint-card">
            <div className="complaint-header">
              <div>
                <span style={{ marginRight: 8 }}>{categoryIcon[c.category] || "📌"}</span>
                <span className="complaint-subject">{c.subject}</span>
              </div>
              <span className={`badge ${statusBadge[c.status] || "badge-info"}`}>{c.status.replace("_", " ")}</span>
            </div>
            <div className="complaint-meta">
              {c.category} • Filed on {new Date(c.created_at).toLocaleDateString()}
            </div>
            <div className="complaint-body">{c.description}</div>
            {c.admin_notes && (
              <div style={{ marginTop: 12, padding: 12, background: "var(--surface)", borderRadius: "var(--radius-md)", fontSize: "0.8rem" }}>
                <strong>Admin Response:</strong> {c.admin_notes}
              </div>
            )}
          </div>
        ))
      )}
    </>
  );
}

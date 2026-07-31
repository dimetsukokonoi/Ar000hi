"use client";
import { useState, useEffect } from "react";

const API = "http://localhost:8000/api";

interface ContactInfo {
  id: string;
  contact_name: string;
  contact_phone: string;
  contact_email: string;
  created_at?: string;
}

interface ShareRecord {
  id: string;
  share_url: string;
  session_id?: string | null;
  contact_count: number;
  created_at: string;
}

export default function TrustedContactsPage() {
  const [contacts, setContacts] = useState<ContactInfo[]>([]);
  const [shares, setShares] = useState<ShareRecord[]>([]);
  const [form, setForm] = useState({ contact_name: "", contact_phone: "", contact_email: "" });
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const showNotice = (type: "success" | "error", text: string) => {
    setNotice({ type, text });
    setTimeout(() => setNotice(null), 5000);
  };

  // Ornab: contacts now persist in the backend trusted_contacts table so the
  // SOS alert flow (which reads from the DB) actually notifies these contacts.
  useEffect(() => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    fetch(`${API}/contacts`, { headers })
      .then(res => res.json())
      .then(data => { if (Array.isArray(data)) setContacts(data); })
      .catch(err => console.error("Failed to load contacts:", err))
      .finally(() => setLoading(false));
    fetch(`${API}/contacts/shares`, { headers })
      .then(res => res.json())
      .then(data => { if (Array.isArray(data)) setShares(data); })
      .catch(() => {});
  }, [token]);

  const addContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    try {
      const res = await fetch(`${API}/contacts`, { method: "POST", headers, body: JSON.stringify(form) });
      const data = await res.json();
      if (res.ok) {
        setForm({ contact_name: "", contact_phone: "", contact_email: "" });
        setShowForm(false);
        setContacts(prev => [...prev, { ...data.contact }]);
        showNotice("success", data.message || "Contact added");
      } else {
        showNotice("error", data.detail || "Failed to add contact");
      }
    } catch (err) {
      showNotice("error", "Network error — could not add contact");
      console.error("Add contact failed:", err);
    }
  };

  const removeContact = async (id: string) => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    try {
      await fetch(`${API}/contacts/${id}`, { method: "DELETE", headers });
      setContacts(prev => prev.filter(c => c.id !== id));
    } catch (err) {
      console.error("Remove contact failed:", err);
    }
  };

  return (
    <>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="page-title">👥 Trusted Contacts</h1>
          <p className="page-subtitle">These contacts will be notified when you trigger an SOS or share your ride</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "✕ Cancel" : "+ Add Contact"}
        </button>
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

      {showForm && (
        <div className="glass-card" style={{ padding: 24, marginBottom: 24, animation: "fadeInUp 0.3s ease" }}>
          <form onSubmit={addContact} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 16, alignItems: "end" }}>
            <div className="input-group">
              <label className="input-label">Name</label>
              <input className="input" placeholder="Contact name" required value={form.contact_name} onChange={e => setForm({ ...form, contact_name: e.target.value })} />
            </div>
            <div className="input-group">
              <label className="input-label">Phone</label>
              <input className="input" placeholder="01XXXXXXXXX" required value={form.contact_phone} onChange={e => setForm({ ...form, contact_phone: e.target.value })} />
            </div>
            <div className="input-group">
              <label className="input-label">Email (optional)</label>
              <input className="input" type="email" placeholder="email@example.com" value={form.contact_email} onChange={e => setForm({ ...form, contact_email: e.target.value })} />
            </div>
            <button type="submit" className="btn btn-primary">Add</button>
          </form>
        </div>
      )}

      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 48 }}><span className="spinner spinner-lg" /></div>
      ) : contacts.length === 0 ? (
        <div style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
          <div style={{ fontSize: "3rem", marginBottom: 16 }}>👥</div>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>No trusted contacts</div>
          <div style={{ fontSize: "0.85rem" }}>Add emergency contacts who will be notified during SOS alerts</div>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {contacts.map(c => (
            <div key={c.id} className="glass-card" style={{ padding: 20, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>{c.contact_name}</div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  📞 {c.contact_phone} {c.contact_email && `• ✉️ ${c.contact_email}`}
                </div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => removeContact(c.id)} style={{ color: "var(--danger)" }}>
                Remove
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Share history (Feature 12 improvement — auditable auto-share log) */}
      {shares.length > 0 && (
        <div className="glass-card" style={{ padding: 20, marginTop: 24 }}>
          <h3 style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: 12 }}>📤 Recent Ride Shares</h3>
          {shares.map(s => (
            <div key={s.id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid rgba(100,120,200,0.06)", fontSize: "0.85rem" }}>
              <span style={{ color: "var(--text-secondary)" }}>
                {new Date(s.created_at).toLocaleString()} · {s.contact_count} contact(s) notified
              </span>
              <code style={{ fontSize: "0.75rem", color: "var(--primary)" }}>{s.share_url}</code>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

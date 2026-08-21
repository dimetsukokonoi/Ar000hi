"use client";
import { useState, useEffect } from "react";

import { API } from "@/lib/api";

interface DriverProfile {
  vehicle_type?: string;
  vehicle_model?: string;
  vehicle_plate?: string;
  verification_status?: string;
  admin_notes?: string;
  nid_document_url?: string;
  license_document_url?: string;
  vehicle_registration_url?: string;
}

export default function DriverVerificationPage() {
  const [status, setStatus] = useState<string>("loading");
  // Feature 7: the driver's public star rating, shown on their own profile
  const [rating, setRating] = useState<{ average: number | null; count: number } | null>(null);
  const [reviews, setReviews] = useState<{ id: string; stars: number; comment: string; reviewer_name: string; route: string }[]>([]);
  const [profile, setProfile] = useState<DriverProfile | null>(null);
  const [form, setForm] = useState({ vehicle_type: "bike", vehicle_model: "", vehicle_plate: "" });
  const [files, setFiles] = useState<{ nid: File | null; license: File | null; vehicle: File | null }>({ nid: null, license: null, vehicle: null });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/drivers/status`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(data => {
        setStatus(data.status);
        setProfile(data.profile);
        setRating(data.rating ?? null);
      })
      .catch(() => setStatus("not_submitted"));

    fetch(`${API}/reviews/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => (r.ok ? r.json() : null))
      .then(d => { if (d) { setRating({ average: d.average, count: d.count }); setReviews(d.reviews || []); } })
      .catch(() => {});
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!files.nid || !files.license || !files.vehicle) {
      setMessage("Please upload all three documents");
      return;
    }
    setLoading(true);
    setMessage("");

    const formData = new FormData();
    formData.append("vehicle_type", form.vehicle_type);
    formData.append("vehicle_model", form.vehicle_model);
    formData.append("vehicle_plate", form.vehicle_plate);
    formData.append("nid_document", files.nid);
    formData.append("license_document", files.license);
    formData.append("vehicle_registration", files.vehicle);

    try {
      const res = await fetch(`${API}/drivers/verify`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Submission failed");
      setMessage(data.message);
      setStatus("pending");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const statusBadge = {
    pending: { className: "badge-warning", text: "⏳ Pending Review" },
    approved: { className: "badge-success", text: "✅ Approved" },
    rejected: { className: "badge-danger", text: "❌ Rejected" },
  };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">🚗 Driver Verification</h1>
        <p className="page-subtitle">Submit your documents to become a verified Arooohi driver</p>
      </div>

      {/* Current Status */}
      {status !== "loading" && status !== "not_submitted" && (
        <div className="glass-card" style={{ padding: 24, marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <span style={{ fontWeight: 600 }}>Verification Status:</span>
            <span className={`badge ${statusBadge[status as keyof typeof statusBadge]?.className || "badge-info"}`}>
              {statusBadge[status as keyof typeof statusBadge]?.text || status}
            </span>
          </div>
          {profile?.admin_notes && (
            <div style={{ padding: 12, background: "var(--surface)", borderRadius: "var(--radius-md)", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              <strong>Admin Notes:</strong> {profile.admin_notes}
            </div>
          )}
          {status === "approved" && (
            <div style={{ marginTop: 12, color: "var(--success)", fontSize: "0.9rem" }}>
              ✅ You are a verified driver! You can now accept rides.
            </div>
          )}
        </div>
      )}

      {/* Feature 7: Driver Rating & Review — average on the driver's profile */}
      {rating && (
        <div className="glass-card" style={{ padding: 24, marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
            <div style={{ textAlign: "center", minWidth: 120 }}>
              <div style={{ fontSize: "2.4rem", fontWeight: 800, color: "var(--warning)", lineHeight: 1 }}>
                {rating.average != null ? rating.average.toFixed(1) : "—"}
              </div>
              <div style={{ fontSize: "1rem", letterSpacing: 2, marginTop: 4 }}>
                {[1, 2, 3, 4, 5].map(s2 => (
                  <span key={s2} style={{ opacity: rating.average != null && s2 <= Math.round(rating.average) ? 1 : 0.25 }}>⭐</span>
                ))}
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", marginTop: 6 }}>
                {rating.count} review{rating.count === 1 ? "" : "s"}
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 220 }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 6 }}>⭐ Your rider rating</h3>
              {rating.count === 0 ? (
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.7 }}>
                  No reviews yet. Passengers can rate you once a ride you drove is completed.
                </p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {reviews.slice(0, 3).map(rv => (
                    <div key={rv.id} style={{ fontSize: "0.82rem", borderLeft: "2px solid var(--surface-border)", paddingLeft: 10 }}>
                      <div style={{ color: "var(--warning)" }}>{"⭐".repeat(rv.stars)}</div>
                      {rv.comment && <div style={{ color: "var(--text-secondary)" }}>&ldquo;{rv.comment}&rdquo;</div>}
                      <div style={{ fontSize: "0.72rem", color: "var(--text-tertiary)" }}>
                        {rv.reviewer_name} · {rv.route}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Submission Form — show if not submitted or rejected */}
      {(status === "not_submitted" || status === "rejected" || status === "loading") && (
        <form onSubmit={handleSubmit}>
          {message && (
            <div style={{ padding: "12px 16px", background: message.includes("success") ? "var(--success-muted)" : "var(--danger-muted)", borderRadius: "var(--radius-md)", color: message.includes("success") ? "var(--success)" : "var(--danger)", fontSize: "0.85rem", marginBottom: 20 }}>
              {message}
            </div>
          )}

          {/* Vehicle Info */}
          <div className="glass-card" style={{ padding: 24, marginBottom: 24 }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 16 }}>🚙 Vehicle Information</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
              <div className="input-group">
                <label className="input-label">Vehicle Type</label>
                <select className="input select" value={form.vehicle_type} onChange={e => setForm({ ...form, vehicle_type: e.target.value })}>
                  <option value="bike">Bike</option>
                  <option value="car">Car</option>
                  <option value="cng">CNG</option>
                </select>
              </div>
              <div className="input-group">
                <label className="input-label">Vehicle Model</label>
                <input className="input" placeholder="e.g. Honda CBR" required value={form.vehicle_model} onChange={e => setForm({ ...form, vehicle_model: e.target.value })} />
              </div>
              <div className="input-group">
                <label className="input-label">License Plate</label>
                <input className="input" placeholder="e.g. DH-12-3456" required value={form.vehicle_plate} onChange={e => setForm({ ...form, vehicle_plate: e.target.value })} />
              </div>
            </div>
          </div>

          {/* Document Uploads */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 24 }}>
            {([
              { key: "nid", label: "National ID (NID)", icon: "🪪" },
              { key: "license", label: "Driving License", icon: "📄" },
              { key: "vehicle", label: "Vehicle Registration", icon: "🚗" },
            ] as const).map(doc => (
              <div key={doc.key} className={`file-upload ${files[doc.key] ? "has-file" : ""}`}>
                <input type="file" accept="image/*,.pdf" onChange={e => {
                  if (e.target.files?.[0]) setFiles({ ...files, [doc.key]: e.target.files[0] });
                }} />
                <div className="file-upload-icon">{doc.icon}</div>
                <div className="file-upload-text">{doc.label}</div>
                {files[doc.key] && <div className="file-upload-name">✓ {files[doc.key]!.name}</div>}
              </div>
            ))}
          </div>

          <button type="submit" className="btn btn-primary btn-lg" disabled={loading}>
            {loading ? <span className="spinner" /> : "📤 Submit for Verification"}
          </button>
        </form>
      )}

      {/* Pending state */}
      {status === "pending" && (
        <div className="glass-card" style={{ padding: 32, textAlign: "center" }}>
          <div style={{ fontSize: "3rem", marginBottom: 16 }}>⏳</div>
          <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: 8 }}>Documents Under Review</h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            A campus moderator will review your documents shortly. You&apos;ll be notified once approved.
          </p>
        </div>
      )}
    </>
  );
}

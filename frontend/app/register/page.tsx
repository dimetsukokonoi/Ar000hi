"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API = "http://localhost:8000/api";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "", gender: "male" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    if (!form.email.endsWith("@g.bracu.ac.bd")) {
      setError("Only @g.bracu.ac.bd emails are allowed. Please use your BRACU student email.");
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Registration failed");

      // Store email for OTP page, also store OTP hint for demo
      localStorage.setItem("pending_email", form.email);
      if (data.otp_hint) localStorage.setItem("otp_hint", data.otp_hint);
      router.push("/verify");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="glass-card auth-card">
        <div style={{ textAlign: "center", marginBottom: 8 }}>
          <Link href="/" style={{ fontSize: "1.5rem", fontWeight: 800, background: "linear-gradient(135deg, var(--primary), var(--accent))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Arooohi
          </Link>
        </div>
        <h1 className="auth-title">Create Account</h1>
        <p className="auth-subtitle">Join the exclusive BRACU ride-sharing network</p>

        {error && (
          <div style={{ padding: "12px 16px", background: "var(--danger-muted)", borderRadius: "var(--radius-md)", color: "var(--danger)", fontSize: "0.85rem", marginBottom: 16 }}>
            ⚠️ {error}
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="input-group">
            <label className="input-label">Full Name</label>
            <input className="input" placeholder="Ahnaf Bin Zakaria" required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          </div>

          <div className="input-group">
            <label className="input-label">BRACU Email</label>
            <input className={`input ${form.email && !form.email.endsWith("@g.bracu.ac.bd") ? "input-error" : ""}`} type="email" placeholder="student@g.bracu.ac.bd" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
            {form.email && !form.email.endsWith("@g.bracu.ac.bd") && (
              <span className="error-text">Must be a @g.bracu.ac.bd email</span>
            )}
          </div>

          <div className="input-group">
            <label className="input-label">Phone Number</label>
            <input className="input" placeholder="01XXXXXXXXX" required value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} />
          </div>

          <div className="input-group">
            <label className="input-label">Gender</label>
            <select className="input select" value={form.gender} onChange={e => setForm({ ...form, gender: e.target.value })}>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div className="input-group">
            <label className="input-label">Password</label>
            <input className="input" type="password" placeholder="Min 6 characters" required minLength={6} value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
          </div>

          <button type="submit" className="btn btn-primary btn-lg" disabled={loading} style={{ width: "100%" }}>
            {loading ? <span className="spinner" /> : "🎓 Register with BRACU Email"}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account? <Link href="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}

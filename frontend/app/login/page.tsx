"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API = "http://localhost:8000/api";

export default function LoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Login failed");

      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));

      if (data.user.role === "admin") {
        router.push("/admin");
      } else {
        router.push("/dashboard");
      }
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
        <h1 className="auth-title">Welcome Back</h1>
        <p className="auth-subtitle">Sign in to your BRACU ride-sharing account</p>

        {error && (
          <div style={{ padding: "12px 16px", background: "var(--danger-muted)", borderRadius: "var(--radius-md)", color: "var(--danger)", fontSize: "0.85rem", marginBottom: 16 }}>
            ⚠️ {error}
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="input-group">
            <label className="input-label">BRACU Email</label>
            <input className="input" type="email" placeholder="student@g.bracu.ac.bd" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
          </div>

          <div className="input-group">
            <label className="input-label">Password</label>
            <input className="input" type="password" placeholder="Enter your password" required value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
          </div>

          <button type="submit" className="btn btn-primary btn-lg" disabled={loading} style={{ width: "100%" }}>
            {loading ? <span className="spinner" /> : "Sign In"}
          </button>
        </form>

        <div className="auth-footer">
          Don&apos;t have an account? <Link href="/register">Register</Link>
        </div>

        <div style={{ marginTop: 24, padding: "16px", background: "var(--surface)", borderRadius: "var(--radius-md)", fontSize: "0.8rem" }}>
          <div style={{ color: "var(--text-tertiary)", marginBottom: 8, fontWeight: 600 }}>Demo Admin Login:</div>
          <div style={{ color: "var(--text-secondary)" }}>Email: <code style={{ color: "var(--primary)" }}>admin@g.bracu.ac.bd</code></div>
          <div style={{ color: "var(--text-secondary)" }}>Password: <code style={{ color: "var(--primary)" }}>admin123</code></div>
        </div>
      </div>
    </div>
  );
}

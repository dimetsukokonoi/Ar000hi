"use client";
import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API = "http://localhost:8000/api";

export default function VerifyPage() {
  const router = useRouter();
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [otpHint, setOtpHint] = useState("");
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    setEmail(localStorage.getItem("pending_email") || "");
    setOtpHint(localStorage.getItem("otp_hint") || "");
    inputRefs.current[0]?.focus();
  }, []);

  const handleChange = (index: number, value: string) => {
    if (value.length > 1) value = value[value.length - 1];
    if (!/^\d*$/.test(value)) return;

    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);

    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const code = otp.join("");

    if (code.length !== 6) {
      setError("Please enter the complete 6-digit code");
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API}/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, code }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Verification failed");

      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));
      localStorage.removeItem("pending_email");
      localStorage.removeItem("otp_hint");
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message);
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
        <h1 className="auth-title">Verify Your Email</h1>
        <p className="auth-subtitle">
          Enter the 6-digit code sent to<br />
          <strong style={{ color: "var(--primary)" }}>{email || "your email"}</strong>
        </p>

        {otpHint && (
          <div style={{ padding: "12px 16px", background: "var(--info-muted)", borderRadius: "var(--radius-md)", color: "var(--info)", fontSize: "0.8rem", textAlign: "center", marginBottom: 16 }}>
            📌 Demo OTP: <strong style={{ fontSize: "1.1rem", letterSpacing: 2 }}>{otpHint}</strong>
          </div>
        )}

        {error && (
          <div style={{ padding: "12px 16px", background: "var(--danger-muted)", borderRadius: "var(--radius-md)", color: "var(--danger)", fontSize: "0.85rem", marginBottom: 16 }}>
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="otp-container">
            {otp.map((digit, i) => (
              <input
                key={i}
                ref={el => { inputRefs.current[i] = el; }}
                className="otp-input"
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                onChange={e => handleChange(i, e.target.value)}
                onKeyDown={e => handleKeyDown(i, e)}
              />
            ))}
          </div>

          <button type="submit" className="btn btn-primary btn-lg" disabled={loading} style={{ width: "100%" }}>
            {loading ? <span className="spinner" /> : "✓ Verify Email"}
          </button>
        </form>

        <div className="auth-footer">
          Didn&apos;t receive the code? <button className="btn btn-ghost btn-sm" onClick={async () => {
            try {
              const res = await fetch(`${API}/auth/resend-otp`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
              const data = await res.json();
              if (data.otp_hint) { setOtpHint(data.otp_hint); localStorage.setItem("otp_hint", data.otp_hint); }
            } catch {}
          }}>Resend OTP</button>
        </div>
      </div>
    </div>
  );
}

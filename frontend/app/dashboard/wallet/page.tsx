"use client";
import { useState, useEffect, useCallback } from "react";

import { API } from "@/lib/api";

// Feature 9: Wallet & bKash Integration (mock gateway, real ledger)

interface Transaction {
  id: string;
  kind: "topup" | "fare" | "payout" | "penalty" | "refund";
  amount: number;
  balance_after: number;
  ride_id: string | null;
  method: string;
  reference: string;
  note: string;
  created_at: string;
}

interface WalletData {
  balance: number;
  currency: string;
  totals: { topped_up: number; earned: number; spent: number; penalties: number };
  transactions: Transaction[];
}

const KIND_META: Record<string, { icon: string; label: string; color: string }> = {
  topup: { icon: "＋", label: "Top-up", color: "var(--success)" },
  payout: { icon: "💸", label: "Ride payout", color: "var(--success)" },
  refund: { icon: "↩", label: "Refund", color: "var(--success)" },
  fare: { icon: "🚗", label: "Ride fare", color: "var(--danger)" },
  penalty: { icon: "⚠️", label: "Cancellation fee", color: "var(--danger)" },
};

const QUICK_AMOUNTS = [100, 250, 500, 1000];

export default function WalletPage() {
  const [wallet, setWallet] = useState<WalletData | null>(null);
  const [amount, setAmount] = useState("");
  const [account, setAccount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [error, setError] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  // setState only ever happens in a promise callback here, never synchronously in
  // the effect body — matches the pattern used by the other dashboard pages.
  const load = useCallback(() => {
    if (!token) return;
    fetch(`${API}/wallet`, {
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    })
      .then(res => (res.ok ? res.json() : Promise.reject(new Error("failed"))))
      .then(setWallet)
      .catch(() => setError("Could not load your wallet right now."));
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const showNotice = (type: "success" | "error", text: string) => {
    setNotice({ type, text });
    setTimeout(() => setNotice(null), 4000);
  };

  const topUp = async (e: React.FormEvent) => {
    e.preventDefault();
    const value = parseFloat(amount);
    if (!value || value <= 0) {
      showNotice("error", "Enter a valid amount to add");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/wallet/topup`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ amount: value, method: "bkash", account }),
      });
      const data = await res.json();
      if (res.ok) {
        showNotice("success", `${data.message} (bKash ref ${data.gateway.trx_id})`);
        setAmount("");
        load();
      } else {
        showNotice("error", data.detail || "Top-up failed");
      }
    } catch {
      showNotice("error", "Network error — could not reach the payment service");
    } finally {
      setSubmitting(false);
    }
  };

  const fmt = (n: number) => `৳${Math.abs(n).toFixed(2)}`;

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">👛 Wallet</h1>
        <p className="page-subtitle">
          Top up with bKash, pay for rides, and track every taka in and out
        </p>
      </div>

      {notice && (
        <div className={`toast toast-${notice.type}`} style={{ marginBottom: 20 }}>
          <span>{notice.type === "success" ? "✅" : "⚠️"}</span>
          <span>{notice.text}</span>
        </div>
      )}

      {error && (
        <div className="glass-card" style={{ textAlign: "center", padding: 48, color: "var(--text-tertiary)" }}>
          <div style={{ fontSize: "3rem", marginBottom: 16 }}>⚠️</div>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)" }}>{error}</div>
        </div>
      )}

      {!error && !wallet && (
        <div style={{ display: "flex", justifyContent: "center", padding: 48 }}>
          <span className="spinner spinner-lg" />
        </div>
      )}

      {wallet && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 20, marginBottom: 24 }}>
            {/* Balance */}
            <div className="glass-card" style={{ padding: 28, background: "linear-gradient(135deg, rgba(99,102,241,0.14), rgba(15,23,42,0.85))" }}>
              <div style={{ fontSize: "0.8rem", color: "var(--text-tertiary)", letterSpacing: 1, textTransform: "uppercase", marginBottom: 8 }}>
                Available balance
              </div>
              <div style={{ fontSize: "2.6rem", fontWeight: 800, color: wallet.balance < 0 ? "var(--danger)" : "var(--text-primary)", lineHeight: 1.1 }}>
                ৳{wallet.balance.toFixed(2)}
              </div>
              {wallet.balance < 0 && (
                <div
                  style={{
                    marginTop: 12, padding: "10px 12px", borderRadius: "var(--radius-md)",
                    background: "rgba(255,59,92,0.12)", border: "1px solid rgba(255,59,92,0.35)",
                  }}
                >
                  <div style={{ fontWeight: 700, color: "var(--danger)", fontSize: "0.85rem", marginBottom: 2 }}>
                    ⚠️ You owe ৳{Math.abs(wallet.balance).toFixed(2)}
                  </div>
                  <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                    A ride fare was charged that your balance could not cover. Top up to
                    settle it — the amount is deducted automatically.
                  </div>
                </div>
              )}
              <div style={{ display: "flex", gap: 18, marginTop: 20, flexWrap: "wrap", fontSize: "0.78rem" }}>
                <span style={{ color: "var(--text-secondary)" }}>Added <strong style={{ color: "var(--success)" }}>{fmt(wallet.totals.topped_up)}</strong></span>
                <span style={{ color: "var(--text-secondary)" }}>Earned <strong style={{ color: "var(--success)" }}>{fmt(wallet.totals.earned)}</strong></span>
                <span style={{ color: "var(--text-secondary)" }}>Spent <strong>{fmt(wallet.totals.spent)}</strong></span>
                <span style={{ color: "var(--text-secondary)" }}>Fees <strong style={{ color: "var(--danger)" }}>{fmt(wallet.totals.penalties)}</strong></span>
              </div>
            </div>

            {/* Top up */}
            <div className="glass-card" style={{ padding: 28 }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 4 }}>Add money</h3>
              <div style={{ fontSize: "0.78rem", color: "var(--text-tertiary)", marginBottom: 16 }}>
                bKash is mocked for this build — no real payment is made.
              </div>
              <form onSubmit={topUp}>
                <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
                  {QUICK_AMOUNTS.map(a => (
                    <button
                      key={a}
                      type="button"
                      className="btn btn-sm btn-ghost"
                      onClick={() => setAmount(String(a))}
                      style={{ borderColor: amount === String(a) ? "var(--primary)" : undefined }}
                    >
                      ৳{a}
                    </button>
                  ))}
                </div>
                <div className="input-group">
                  <label className="input-label">Amount (BDT)</label>
                  <input
                    className="input"
                    type="number"
                    min="10"
                    step="1"
                    placeholder="e.g. 500"
                    value={amount}
                    onChange={e => setAmount(e.target.value)}
                  />
                </div>
                <div className="input-group">
                  <label className="input-label">bKash number (optional)</label>
                  <input
                    className="input"
                    placeholder="01XXXXXXXXX"
                    value={account}
                    onChange={e => setAccount(e.target.value)}
                  />
                </div>
                <button className="btn btn-primary" style={{ width: "100%" }} disabled={submitting}>
                  {submitting ? <span className="spinner" /> : "Top up with bKash"}
                </button>
              </form>
            </div>
          </div>

          {/* Ledger */}
          <div className="glass-card" style={{ padding: 20 }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 4 }}>Transaction history</h3>
            <div style={{ fontSize: "0.78rem", color: "var(--text-tertiary)", marginBottom: 12 }}>
              Every entry records the balance it produced, so the running total is always auditable.
            </div>

            {wallet.transactions.length === 0 && (
              <div style={{ textAlign: "center", padding: 32, color: "var(--text-tertiary)", fontSize: "0.85rem" }}>
                No transactions yet — add some money to get started.
              </div>
            )}

            {wallet.transactions.map(t => {
              const meta = KIND_META[t.kind] || { icon: "•", label: t.kind, color: "var(--text-secondary)" };
              const credit = t.amount > 0;
              return (
                <div
                  key={t.id}
                  style={{
                    display: "flex", alignItems: "center", gap: 12, padding: "12px 0",
                    borderBottom: "1px solid rgba(100,120,200,0.06)",
                  }}
                >
                  <span style={{ fontSize: "1.1rem", width: 28, textAlign: "center" }}>{meta.icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: "0.88rem" }}>{meta.label}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {t.note || "—"}
                      {t.reference ? ` · ref ${t.reference}` : ""}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontWeight: 700, color: credit ? "var(--success)" : "var(--danger)", fontSize: "0.9rem" }}>
                      {credit ? "+" : "−"}{fmt(t.amount)}
                    </div>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-tertiary)" }}>
                      bal ৳{t.balance_after.toFixed(2)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}

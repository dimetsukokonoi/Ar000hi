"use client";
import { useCallback, useEffect, useMemo, useState } from "react";

import { API } from "@/lib/api";

// Feature 9: Wallet & bKash Integration
// Prepaid wallet — the gateway is only touched at the edges (top-up, cash-out).
// Ride fares settle internally, so this page never talks to bKash for a ride.

interface Transaction {
  id: string;
  kind: "topup" | "ride_debit" | "ride_credit" | "withdrawal" | "refund" | "commission";
  amount: number;
  platform_fee: number;
  balance_after: number;
  ride_id: string | null;
  payment_id: string | null;
  note: string;
  created_at: string;
}

interface WalletInfo {
  balance: number;
  currency: string;
  recent: Transaction[];
}

interface Reconciliation {
  stored_balance: number;
  ledger_sum: number;
  difference: number;
  transaction_count: number;
  status: string;
}

const KIND_META: Record<Transaction["kind"], { label: string; icon: string; badge: string }> = {
  topup: { label: "bKash Top-up", icon: "💳", badge: "badge-success" },
  ride_debit: { label: "Ride Fare", icon: "🚗", badge: "badge-warning" },
  ride_credit: { label: "Ride Earnings", icon: "💰", badge: "badge-success" },
  withdrawal: { label: "Cash-out to bKash", icon: "🏦", badge: "badge-info" },
  refund: { label: "Refund", icon: "↩️", badge: "badge-info" },
  commission: { label: "Platform Fee", icon: "🏷️", badge: "badge-danger" },
};

const QUICK_AMOUNTS = [100, 200, 500, 1000];

export default function WalletPage() {
  const [wallet, setWallet] = useState<WalletInfo | null>(null);
  const [history, setHistory] = useState<Transaction[]>([]);
  const [recon, setRecon] = useState<Reconciliation | null>(null);
  const [amount, setAmount] = useState("500");
  const [cashOut, setCashOut] = useState("");
  const [cashNumber, setCashNumber] = useState("");
  const [busy, setBusy] = useState(false);
  // Read the one-shot flash left by the gateway callback page as INITIAL state
  // rather than in an effect.
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(() => {
    if (typeof window === "undefined") return null;
    const flash = sessionStorage.getItem("wallet_flash");
    if (!flash) return null;
    sessionStorage.removeItem("wallet_flash");
    try {
      return JSON.parse(flash) as { type: "success" | "error"; text: string };
    } catch {
      return null;
    }
  });

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token]
  );

  // Pure fetch — returns data instead of setting state, so the effect below can
  // do its setState inside a promise callback (react-hooks/set-state-in-effect).
  const fetchWallet = useCallback(async () => {
    const [w, h] = await Promise.all([
      fetch(`${API}/wallet`, { headers }).then(r => r.json()),
      fetch(`${API}/wallet/transactions?limit=50`, { headers }).then(r => r.json()),
    ]);
    return { w: w as WalletInfo, h: (Array.isArray(h) ? h : []) as Transaction[] };
  }, [headers]);

  const load = useCallback(async () => {
    const { w, h } = await fetchWallet();
    setWallet(w);
    setHistory(h);
  }, [fetchWallet]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchWallet()
      .then(({ w, h }) => {
        if (cancelled) return;
        setWallet(w);
        setHistory(h);
      })
      .catch(() => {
        if (!cancelled) setNotice({ type: "error", text: "Could not load your wallet." });
      });
    return () => { cancelled = true; };
  }, [token, fetchWallet]);

  // Step 1+2 of the bKash flow: create the payment, then hand the browser to the
  // gateway. Nothing is credited here — only the server-side execute can do that.
  const startTopUp = async () => {
    const value = Number(amount);
    if (!Number.isFinite(value) || value < 10) {
      setNotice({ type: "error", text: "Enter an amount of at least 10 BDT." });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const res = await fetch(`${API}/wallet/topup`, {
        method: "POST", headers, body: JSON.stringify({ amount: value }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not start the top-up");
      // Leave Arooohi for the gateway's own page — exactly as a real checkout does.
      window.location.href = data.checkout_url;
    } catch (err) {
      setNotice({ type: "error", text: err instanceof Error ? err.message : String(err) });
      setBusy(false);
    }
  };

  const withdraw = async () => {
    const value = Number(cashOut);
    if (!Number.isFinite(value) || value <= 0) {
      setNotice({ type: "error", text: "Enter a withdrawal amount." });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const res = await fetch(`${API}/wallet/withdraw`, {
        method: "POST", headers,
        body: JSON.stringify({ amount: value, wallet_number: cashNumber }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Withdrawal failed");
      setNotice({ type: "success", text: data.message });
      setCashOut("");
      await load();
    } catch (err) {
      setNotice({ type: "error", text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  };

  const runReconcile = async () => {
    try {
      const res = await fetch(`${API}/wallet/reconcile`, { headers });
      setRecon(await res.json());
    } catch {
      setNotice({ type: "error", text: "Reconciliation check failed." });
    }
  };

  if (!wallet) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 64 }}>
        <span className="spinner spinner-lg" />
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">💳 Wallet</h1>
        <p className="page-subtitle">
          Top up with bKash, pay for rides automatically, and cash out your earnings.
        </p>
      </div>

      {notice && (
        <div
          style={{
            padding: "12px 16px", marginBottom: 20, fontSize: "0.88rem",
            borderRadius: "var(--radius-md)",
            background: notice.type === "success" ? "var(--success-muted)" : "var(--danger-muted)",
            color: notice.type === "success" ? "var(--success)" : "var(--danger)",
          }}
        >
          {notice.type === "success" ? "✅ " : "⚠️ "}{notice.text}
        </div>
      )}

      {/* Balance */}
      <div className="glass-card" style={{ padding: 28, marginBottom: 20 }}>
        <div style={{ fontSize: "0.78rem", color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
          Available Balance
        </div>
        <div style={{ fontSize: "2.8rem", fontWeight: 800, color: "var(--primary)", margin: "6px 0 2px" }}>
          ৳ {wallet.balance.toFixed(2)}
        </div>
        <div style={{ fontSize: "0.8rem", color: "var(--text-tertiary)" }}>
          {history.length} transaction{history.length === 1 ? "" : "s"} on record
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 20, marginBottom: 20 }}>
        {/* Top up */}
        <div className="glass-card" style={{ padding: 24 }}>
          <h2 style={{ fontSize: "1.05rem", marginBottom: 4 }}>Add Money</h2>
          <p style={{ fontSize: "0.8rem", color: "var(--text-tertiary)", marginBottom: 16 }}>
            You&apos;ll be taken to bKash to confirm, then returned here.
          </p>

          <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
            {QUICK_AMOUNTS.map(v => (
              <button
                key={v}
                onClick={() => setAmount(String(v))}
                className={`btn btn-sm ${Number(amount) === v ? "btn-primary" : "btn-ghost"}`}
              >
                ৳{v}
              </button>
            ))}
          </div>

          <div className="input-group">
            <label className="input-label">Amount (BDT)</label>
            <input
              className="input" type="number" min={10} max={25000} value={amount}
              onChange={e => setAmount(e.target.value)} placeholder="500"
            />
          </div>

          <button onClick={startTopUp} disabled={busy} className="btn btn-primary" style={{ width: "100%" }}>
            {busy ? <span className="spinner" /> : "Continue to bKash"}
          </button>
        </div>

        {/* Cash out */}
        <div className="glass-card" style={{ padding: 24 }}>
          <h2 style={{ fontSize: "1.05rem", marginBottom: 4 }}>Cash Out</h2>
          <p style={{ fontSize: "0.8rem", color: "var(--text-tertiary)", marginBottom: 16 }}>
            Send your ride earnings back to your bKash account.
          </p>

          <div className="input-group">
            <label className="input-label">Amount (BDT)</label>
            <input
              className="input" type="number" min={1} value={cashOut}
              onChange={e => setCashOut(e.target.value)} placeholder="0.00"
            />
          </div>
          <div className="input-group">
            <label className="input-label">bKash Number</label>
            <input
              className="input" value={cashNumber}
              onChange={e => setCashNumber(e.target.value)} placeholder="01XXXXXXXXX"
            />
          </div>

          <button onClick={withdraw} disabled={busy || wallet.balance <= 0}
                  className="btn btn-secondary" style={{ width: "100%" }}>
            Withdraw
          </button>
        </div>
      </div>

      {/* Ledger */}
      <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
          <h2 style={{ fontSize: "1.05rem" }}>Transaction History</h2>
          <button onClick={runReconcile} className="btn btn-ghost btn-sm">Verify ledger</button>
        </div>

        {recon && (
          <div
            style={{
              padding: "10px 14px", marginBottom: 14, fontSize: "0.8rem",
              borderRadius: "var(--radius-md)",
              background: recon.status === "balanced" ? "var(--success-muted)" : "var(--danger-muted)",
              color: recon.status === "balanced" ? "var(--success)" : "var(--danger)",
            }}
          >
            {recon.status === "balanced" ? "✅ Balanced" : "⚠️ MISMATCH"} — stored ৳{recon.stored_balance.toFixed(2)} vs
            ledger ৳{recon.ledger_sum.toFixed(2)} across {recon.transaction_count} entries
            (difference ৳{recon.difference.toFixed(2)})
          </div>
        )}

        {history.length === 0 ? (
          <p style={{ color: "var(--text-tertiary)", fontSize: "0.88rem" }}>
            No transactions yet — add money to get started.
          </p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Type</th><th>Note</th><th style={{ textAlign: "right" }}>Amount</th>
                  <th style={{ textAlign: "right" }}>Balance</th><th>When</th>
                </tr>
              </thead>
              <tbody>
                {history.map(t => {
                  const meta = KIND_META[t.kind] ?? { label: t.kind, icon: "•", badge: "badge-info" };
                  const positive = t.amount >= 0;
                  return (
                    <tr key={t.id}>
                      <td><span className={`badge ${meta.badge}`}>{meta.icon} {meta.label}</span></td>
                      <td style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>{t.note || "—"}</td>
                      <td style={{ textAlign: "right", fontWeight: 700, color: positive ? "var(--success)" : "var(--danger)" }}>
                        {positive ? "+" : "−"}৳{Math.abs(t.amount).toFixed(2)}
                      </td>
                      <td style={{ textAlign: "right", color: "var(--text-tertiary)" }}>
                        ৳{t.balance_after.toFixed(2)}
                      </td>
                      <td style={{ fontSize: "0.78rem", color: "var(--text-tertiary)" }}>
                        {new Date(t.created_at + "Z").toLocaleString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <p style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", lineHeight: 1.7 }}>
        <strong>Demo mode.</strong> Payments run against a simulated bKash gateway that
        implements the real tokenized-checkout flow (grant token → create → redirect →
        execute → query). No real money moves. Test accounts:{" "}
        <code>01770000001</code> succeeds, <code>01770000002</code> fails,{" "}
        <code>01770000003</code> times out, <code>01770000004</code> cancels.
      </p>
    </div>
  );
}

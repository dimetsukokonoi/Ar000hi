"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { API } from "@/lib/api";

// Feature 9: the merchant-side return leg of the bKash checkout.
//
// The gateway sends the browser back here with ?paymentID=…&status=…
// That status is NOT trusted — anyone can type this URL. The page's only job is
// to ask OUR server to run execute_payment(), which is the single place a
// top-up can actually be credited.

type Phase = "verifying" | "success" | "failed";

function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const paymentId = params.get("paymentID");
  const gatewayStatus = params.get("status");

  // Derived from the URL at first render, so the effect never has to setState
  // synchronously for the missing-reference case.
  const [phase, setPhase] = useState<Phase>(paymentId ? "verifying" : "failed");
  const [message, setMessage] = useState(
    paymentId
      ? "Confirming your payment with bKash…"
      : "No payment reference was returned by the gateway."
  );
  const [amount, setAmount] = useState<number | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    // React strict mode mounts effects twice in dev; execute must run once.
    if (ran.current) return;
    ran.current = true;

    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }

    if (!paymentId) return;   // already reflected in the initial state

    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

    (async () => {
      try {
        const res = await fetch(`${API}/wallet/topup/execute`, {
          method: "POST", headers, body: JSON.stringify({ payment_id: paymentId }),
        });
        const data = await res.json();

        if (!res.ok) {
          setPhase("failed");
          setMessage(data.detail || `Payment ${gatewayStatus || "failed"}.`);
          return;
        }

        setPhase("success");
        setAmount(data.amount);
        setMessage(
          data.duplicate
            ? "This payment was already credited to your wallet."
            : `৳${Number(data.amount).toFixed(2)} added to your wallet.`
        );
      } catch {
        setPhase("failed");
        setMessage("Could not reach the server to confirm your payment.");
      }
    })();
  }, [paymentId, gatewayStatus, router]);

  const goBack = () => {
    sessionStorage.setItem(
      "wallet_flash",
      JSON.stringify({
        type: phase === "success" ? "success" : "error",
        text: message,
      })
    );
    router.push("/dashboard/wallet");
  };

  const tone =
    phase === "success" ? "var(--success)" : phase === "failed" ? "var(--danger)" : "var(--primary)";

  return (
    <div className="auth-container">
      <div className="glass-card auth-card" style={{ textAlign: "center" }}>
        <div style={{ fontSize: "3rem", marginBottom: 12 }}>
          {phase === "verifying" ? <span className="spinner spinner-lg" /> : phase === "success" ? "✅" : "⚠️"}
        </div>

        <h1 className="auth-title" style={{ color: tone }}>
          {phase === "verifying" ? "Verifying Payment" : phase === "success" ? "Top-up Complete" : "Payment Not Completed"}
        </h1>

        <p className="auth-subtitle" style={{ marginBottom: 20 }}>{message}</p>

        {phase === "success" && amount !== null && (
          <div style={{ fontSize: "2rem", fontWeight: 800, color: "var(--success)", marginBottom: 20 }}>
            + ৳{amount.toFixed(2)}
          </div>
        )}

        {paymentId && (
          <div style={{ fontSize: "0.72rem", color: "var(--text-tertiary)", marginBottom: 20 }}>
            Reference: <code>{paymentId}</code>
          </div>
        )}

        {phase !== "verifying" && (
          <button onClick={goBack} className="btn btn-primary btn-lg" style={{ width: "100%" }}>
            Back to Wallet
          </button>
        )}
      </div>
    </div>
  );
}

export default function WalletCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="auth-container">
          <div className="glass-card auth-card" style={{ textAlign: "center" }}>
            <span className="spinner spinner-lg" />
          </div>
        </div>
      }
    >
      <CallbackInner />
    </Suspense>
  );
}

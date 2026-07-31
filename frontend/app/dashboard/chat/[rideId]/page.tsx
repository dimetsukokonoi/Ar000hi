"use client";
import { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";

const API = "http://localhost:8000/api";
const WS = "ws://localhost:8000/ws";

interface ChatMessage {
  id: string;
  ride_id: string;
  sender_id: string;
  sender_name: string;
  message: string;
  created_at: string;
}

interface MeInfo {
  id: string;
  name: string;
}

// Ornab: Ride Chat (Feature 15) — real-time via WebSocket, persisted to backend
export default function RideChatPage() {
  const params = useParams<{ rideId: string }>();
  const rideId = params.rideId;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [me] = useState<MeInfo | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      const raw = localStorage.getItem("user");
      return raw ? (JSON.parse(raw) as MeInfo) : null;
    } catch {
      return null;
    }
  });
  const [connected, setConnected] = useState(false);
  const [fatalError, setFatalError] = useState("");
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  // Load history once
  useEffect(() => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    fetch(`${API}/rides/${rideId}/messages`, { headers })
      .then(res => {
        if (res.status === 403) {
          setFatalError("You're not a participant of this ride, so the chat is unavailable.");
          return [];
        }
        if (res.status === 404) {
          setFatalError("This ride no longer exists.");
          return [];
        }
        return res.ok ? res.json() : [];
      })
      .then(setMessages)
      .catch(err => console.error("Failed to load chat history:", err));
  }, [token, rideId]);

  // WebSocket connection (connect once per ride, auto-reconnect on drop)
  useEffect(() => {
    if (!token) return;
    let closedByUser = false;
    let retryTimer: NodeJS.Timeout | null = null;

    const connect = () => {
      const ws = new WebSocket(`${WS}/chat/${rideId}?token=${token}`);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "rate_limited") return; // server throttle hint; keep UX calm
          setMessages(prev => [...prev, msg]);
        } catch (err) {
          console.error("Bad WS message:", err);
        }
      };
      ws.onclose = (ev) => {
        setConnected(false);
        // 4401 = bad/expired token, 4403 = not a ride participant — terminal, explain.
        if (ev.code === 4401 || ev.code === 4403) {
          setFatalError(
            ev.code === 4403
              ? "You're not a participant of this ride, so the chat is unavailable."
              : "Your session expired. Please log in again."
          );
          return;
        }
        if (!closedByUser) {
          retryTimer = setTimeout(connect, 3000);
        }
      };
      ws.onerror = () => ws.close();
    };

    connect();

    return () => {
      closedByUser = true;
      if (retryTimer) clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, [rideId, token]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ message: trimmed }));
    setText("");
  };

  return (
    <>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="page-title">💬 Ride Chat</h1>
          <p className="page-subtitle">Secure in-app messaging — no phone numbers shared</p>
        </div>
        <span className={`badge ${connected ? "badge-success" : "badge-danger"}`}>
          {connected ? "● Connected" : "○ Disconnected"}
        </span>
      </div>

      {fatalError ? (
        <div className="glass-card" style={{ textAlign: "center", padding: 48 }}>
          <div style={{ fontSize: "3rem", marginBottom: 16 }}>🔒</div>
          <div style={{ fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Chat Unavailable</div>
          <p style={{ fontSize: "0.9rem", color: "var(--text-tertiary)", maxWidth: 420, margin: "0 auto" }}>
            {fatalError}
          </p>
        </div>
      ) : (
      <div className="glass-card" style={{ display: "flex", flexDirection: "column", height: "60vh", padding: 0, overflow: "hidden" }}>
        <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 12 }}>
          {messages.length === 0 && (
            <div style={{ textAlign: "center", color: "var(--text-tertiary)", marginTop: 40, fontSize: "0.9rem" }}>
              No messages yet — say hi to your ride partner 👋
            </div>
          )}
          {messages.map(m => {
            const mine = m.sender_id === me?.id;
            return (
              <div key={m.id} style={{ display: "flex", justifyContent: mine ? "flex-end" : "flex-start" }}>
                <div style={{
                  maxWidth: "70%",
                  padding: "10px 14px",
                  borderRadius: 16,
                  background: mine ? "var(--primary-muted)" : "var(--surface)",
                  border: mine ? "1px solid rgba(0,212,170,0.3)" : "1px solid var(--surface-border)",
                }}>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-tertiary)", marginBottom: 2 }}>
                    {mine ? "You" : m.sender_name}
                  </div>
                  <div style={{ fontSize: "0.9rem" }}>{m.message}</div>
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={sendMessage} style={{ display: "flex", gap: 12, padding: 16, borderTop: "1px solid var(--surface-border)" }}>
          <input
            className="input"
            placeholder="Type a message..."
            value={text}
            onChange={e => setText(e.target.value)}
            autoFocus
          />
          <button type="submit" className="btn btn-primary" disabled={!connected}>Send</button>
        </form>
      </div>
      )}
    </>
  );
}

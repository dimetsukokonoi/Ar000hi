"use client";
import { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";

const API = "http://localhost:8000/api";
const WS = "ws://localhost:8000/ws";

// Ornab: Ride Chat (Feature 15) — real-time via WebSocket, persisted to backend
export default function RideChatPage() {
  const params = useParams<{ rideId: string }>();
  const rideId = params.rideId;
  const [messages, setMessages] = useState<any[]>([]);
  const [text, setText] = useState("");
  const [me, setMe] = useState<any>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  useEffect(() => {
    if (typeof window === "undefined") return;
    const userData = localStorage.getItem("user");
    if (userData) setMe(JSON.parse(userData));
  }, []);

  // Load history once
  useEffect(() => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    fetch(`${API}/rides/${rideId}/messages`, { headers })
      .then(res => res.ok ? res.json() : [])
      .then(setMessages)
      .catch(err => console.error("Failed to load chat history:", err));
  }, [token, rideId]);

  // WebSocket connection (connect once per ride)
  useEffect(() => {
    if (!token) return;
    const ws = new WebSocket(`${WS}/chat/${rideId}?token=${token}`);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        setMessages(prev => [...prev, msg]);
      } catch (err) {
        console.error("Bad WS message:", err);
      }
    };
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    return () => { ws.close(); };
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
    </>
  );
}

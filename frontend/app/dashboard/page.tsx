"use client";
import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";

import { API } from "@/lib/api";

interface SessionInfo {
  session_id: string;
  id?: string;
  share_url?: string;
  is_active?: boolean;
  created_at?: string;
}

interface TrackingPoint {
  lat: number;
  lng: number;
  created_at: string;
}

interface SosResult {
  location?: { lat: number; lng: number };
  contacts_notified?: { name: string; phone: string }[];
  message?: string;
}

// Dynamically import the map to avoid SSR issues with leaflet
const TrackingMap = dynamic(() => import("@/components/TrackingMap"), { ssr: false, loading: () => <div style={{ height: 500, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--surface)", borderRadius: "var(--radius-lg)" }}><span className="spinner spinner-lg" /></div> });

export default function DashboardPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [points, setPoints] = useState<TrackingPoint[]>([]);
  const [currentPos, setCurrentPos] = useState<{ lat: number; lng: number }>({ lat: 23.7745, lng: 90.4253 });
  const [tracking, setTracking] = useState(false);
  const [copied, setCopied] = useState(false);
  const [sosModal, setSosModal] = useState(false);
  const [sosSent, setSosSent] = useState(false);
  const [sosResult, setSosResult] = useState<SosResult | null>(null);
  const watchId = useRef<number | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const sessionRef = useRef<SessionInfo | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token]
  );

  // Cleanup: never leave the geolocation watch / demo interval running on unmount.
  useEffect(() => {
    return () => {
      if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  // Single source of truth for recording a point (GPS or demo walk).
  const recordPoint = useCallback(async (pos: { lat: number; lng: number }) => {
    if (!sessionRef.current) return;
    setCurrentPos(pos);
    setPoints(prev => {
      const next = [...prev, { ...pos, created_at: new Date().toISOString() }];
      return next.length > 300 ? next.slice(-300) : next; // cap client buffer
    });
    try {
      await fetch(`${API}/tracking/point`, {
        method: "POST",
        headers,
        body: JSON.stringify({ session_id: sessionRef.current.session_id, lat: pos.lat, lng: pos.lng }),
      });
    } catch { /* best-effort point upload */ }
  }, [headers]);

  // Get current position
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setCurrentPos({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        () => {}
      );
    }
  }, []);

  // Check for existing active session
  useEffect(() => {
    if (!token) return;
    const h = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    fetch(`${API}/tracking/active`, { headers: h }).then(r => r.json()).then(data => {
      if (data.session) { setSession(data.session); sessionRef.current = data.session; }
    }).catch(() => {});
  }, [token]);

  const startTracking = async () => {
    try {
      const res = await fetch(`${API}/tracking/session`, { method: "POST", headers });
      const data = await res.json();
      setSession(data);
      sessionRef.current = data;
      setTracking(true);
      setPoints([]);

      // Ornab (Feature 12): auto-share ride details to trusted contacts when tracking starts
      if (data.share_url) {
        fetch(`${API}/contacts/auto-share`, {
          method: "POST",
          headers,
          body: JSON.stringify({ share_url: data.share_url, session_id: data.session_id }),
        }).catch(() => {});
      }

      // One source of truth: prefer real GPS; fall back to a gentle demo walk so the
      // map still moves when no hardware signal arrives. (Previously BOTH ran → duplicates.)
      let gpsActive = false;
      if (navigator.geolocation) {
        watchId.current = navigator.geolocation.watchPosition(
          (pos) => { gpsActive = true; recordPoint({ lat: pos.coords.latitude, lng: pos.coords.longitude }); },
          () => {},
          { enableHighAccuracy: true, maximumAge: 3000 }
        );
      }

      intervalRef.current = setInterval(() => {
        if (gpsActive) return; // real GPS already updating
        setCurrentPos(prev => {
          if (!prev) return prev;
          const newPos = {
            lat: prev.lat + (Math.random() - 0.5) * 0.001,
            lng: prev.lng + (Math.random() - 0.5) * 0.001,
          };
          recordPoint(newPos);
          return newPos;
        });
      }, 5000);
    } catch (err) {
      console.error("Failed to start tracking:", err);
    }
  };

  const stopTracking = async () => {
    if (watchId.current !== null) {
      navigator.geolocation.clearWatch(watchId.current);
      watchId.current = null;
    }
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (sessionRef.current) {
      await fetch(`${API}/tracking/session/${sessionRef.current.session_id || sessionRef.current.id}/stop`, { method: "POST", headers }).catch(() => {});
    }
    sessionRef.current = null;
    setTracking(false);
    setSession(null);
  };

  const copyShareLink = () => {
    if (session?.share_url) {
      navigator.clipboard.writeText(session.share_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const triggerSOS = async () => {
    if (!currentPos) return;
    try {
      const res = await fetch(`${API}/sos/trigger`, {
        method: "POST",
        headers,
        body: JSON.stringify({ lat: currentPos.lat, lng: currentPos.lng, session_id: sessionRef.current?.session_id || session?.session_id }),
      });
      const data = await res.json();
      setSosResult(data);
      setSosSent(true);
    } catch (err) {
      console.error("SOS failed:", err);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">🗺️ Ride Tracking</h1>
        <p className="page-subtitle">Track your ride in real-time and share your location with trusted contacts</p>
      </div>

      {/* Controls */}
      <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap", alignItems: "center" }}>
        {!tracking ? (
          <button className="btn btn-primary" onClick={startTracking}>
            📍 Start Live Tracking
          </button>
        ) : (
          <button className="btn btn-danger" onClick={stopTracking}>
            ⏹ Stop Tracking
          </button>
        )}

        {session && (
          <button className="btn btn-secondary" onClick={copyShareLink}>
            {copied ? "✓ Link Copied!" : "🔗 Share Location"}
          </button>
        )}

        {currentPos && (
          <span style={{ fontSize: "0.8rem", color: "var(--text-tertiary)" }}>
            📍 {currentPos.lat.toFixed(4)}, {currentPos.lng.toFixed(4)}
          </span>
        )}

        {tracking && (
          <span className="badge badge-success" style={{ animation: "sosPulse 2s infinite" }}>
            ● LIVE
          </span>
        )}
      </div>

      {/* Share URL */}
      {session?.share_url && (
        <div className="glass-card" style={{ padding: 16, marginBottom: 24, display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Share link:</span>
          <code style={{ fontSize: "0.8rem", color: "var(--primary)", flex: 1 }}>{session.share_url}</code>
          <button className="btn btn-sm btn-secondary" onClick={copyShareLink}>{copied ? "Copied!" : "Copy"}</button>
        </div>
      )}

      {/* Map — keyed by session so a fresh tracking session resets map auto-follow */}
      <div style={{ marginBottom: 24 }}>
        <TrackingMap key={session?.session_id || "idle"} center={currentPos || { lat: 23.7781, lng: 90.4042 }} points={points} currentPos={currentPos} isTracking={tracking} />
      </div>

      {/* Campus Hotspots Legend */}
      <div className="glass-card" style={{ padding: 20 }}>
        <h3 style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: 12 }}>🏫 Campus Hotspots</h3>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
          {["Gate 1", "Gate 2", "Library", "Cafeteria", "UB Building", "Residential"].map(h => (
            <span key={h} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--primary)", display: "inline-block" }} />
              {h}
            </span>
          ))}
        </div>
      </div>

      {/* SOS Button */}
      <button className="sos-button" onClick={() => setSosModal(true)} title="Emergency SOS">
        SOS
      </button>

      {/* SOS Modal */}
      {sosModal && !sosSent && (
        <div className="modal-backdrop" onClick={() => setSosModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div style={{ textAlign: "center", fontSize: "3rem", marginBottom: 16 }}>🆘</div>
            <h2 className="modal-title" style={{ textAlign: "center", color: "var(--danger)" }}>Trigger SOS Alert?</h2>
            <p className="modal-text" style={{ textAlign: "center" }}>
              This will immediately alert <strong>campus security</strong> and all your <strong>trusted contacts</strong> with your current location.
            </p>
            <div className="modal-actions" style={{ justifyContent: "center" }}>
              <button className="btn btn-ghost" onClick={() => setSosModal(false)}>Cancel</button>
              <button className="btn btn-danger btn-lg" onClick={triggerSOS}>
                🆘 Send SOS Alert
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SOS Sent Confirmation */}
      {sosSent && (
        <div className="modal-backdrop" onClick={() => { setSosSent(false); setSosModal(false); }}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 520 }}>
            <div style={{ textAlign: "center", fontSize: "3rem", marginBottom: 16 }}>✅</div>
            <h2 className="modal-title" style={{ textAlign: "center", color: "var(--success)" }}>SOS Alert Sent!</h2>
            <p className="modal-text" style={{ textAlign: "center" }}>
              Your emergency contacts and campus security have been notified.
            </p>

            {sosResult && (
              <div style={{ marginBottom: 24 }}>
                <div style={{ fontSize: "0.8rem", color: "var(--text-tertiary)", marginBottom: 8 }}>📍 Location shared: {sosResult.location?.lat.toFixed(4)}, {sosResult.location?.lng.toFixed(4)}</div>
                <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 8 }}>Contacts notified:</div>
                {sosResult.contacts_notified?.map((c, i) => (
                  <div key={i} style={{ padding: "8px 12px", background: "var(--surface)", borderRadius: "var(--radius-md)", marginBottom: 6, fontSize: "0.8rem" }}>
                    <strong>{c.name}</strong> — {c.phone}
                  </div>
                ))}
              </div>
            )}

            <div className="modal-actions" style={{ justifyContent: "center" }}>
              <button className="btn btn-primary" onClick={() => { setSosSent(false); setSosModal(false); }}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

"use client";
import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import Link from "next/link";

const API = "http://localhost:8000/api";

interface TrackingPoint {
  lat: number;
  lng: number;
  created_at: string;
}

interface TrackingData {
  is_active: boolean;
  user_name?: string;
  started_at?: string;
  points: TrackingPoint[];
  latest?: { lat: number; lng: number };
}

const TrackingMap = dynamic(() => import("@/components/TrackingMap"), { ssr: false, loading: () => <div style={{ height: "80vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--surface)" }}><span className="spinner spinner-lg" /></div> });

export default function SharedTrackingPage() {
  const params = useParams();
  const token = params.token as string;
  const [data, setData] = useState<TrackingData | null>(null);
  const [error, setError] = useState("");

  const fetchData = useCallback(() => {
    fetch(`${API}/tracking/share/${token}`)
      .then(r => { if (!r.ok) throw new Error("not found"); return r.json(); })
      .then(setData)
      .catch(() => setError("Tracking session not found or has ended."));
  }, [token]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, [fetchData]);

  if (error) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 16, padding: 24 }}>
        <div style={{ fontSize: "3rem" }}>📍</div>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700 }}>Tracking Unavailable</h1>
        <p style={{ color: "var(--text-secondary)" }}>{error}</p>
        <Link href="/" className="btn btn-primary">Go to Arooohi</Link>
      </div>
    );
  }

  if (!data) {
    return <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}><span className="spinner spinner-lg" /></div>;
  }

  const latest = data.latest || (data.points.length > 0 ? data.points[data.points.length - 1] : { lat: 23.7781, lng: 90.4042 });

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
      {/* Header bar */}
      <div style={{ padding: "16px 24px", background: "var(--bg-secondary)", borderBottom: "1px solid var(--surface-border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <span style={{ fontWeight: 800, background: "linear-gradient(135deg, var(--primary), var(--accent))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Arooohi</span>
          <span style={{ color: "var(--text-tertiary)", fontSize: "0.85rem", marginLeft: 12 }}>Live Tracking</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {data.is_active && <span className="badge badge-success" style={{ animation: "sosPulse 2s infinite" }}>● LIVE</span>}
          {!data.is_active && <span className="badge badge-accent">Ended</span>}
        </div>
      </div>

      {/* User info */}
      <div style={{ padding: "16px 24px", display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 40, height: 40, borderRadius: "50%", background: "var(--primary-muted)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, color: "var(--primary)" }}>
          {data.user_name?.charAt(0)?.toUpperCase()}
        </div>
        <div>
          <div style={{ fontWeight: 600 }}>{data.user_name}</div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-tertiary)" }}>
            Started {data.started_at ? new Date(data.started_at).toLocaleTimeString() : "—"} • {data.points.length} points tracked
          </div>
        </div>
      </div>

      {/* Map */}
      <div style={{ padding: "0 24px 24px" }}>
        <TrackingMap
          center={latest}
          points={data.points}
          currentPos={latest}
          isTracking={data.is_active}
        />
      </div>
    </div>
  );
}

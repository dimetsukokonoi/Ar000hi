"use client";
import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap, Circle } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix leaflet marker icons
const userIcon = new L.DivIcon({
  className: "",
  html: `<div style="width:20px;height:20px;background:var(--primary,#00d4aa);border-radius:50%;border:3px solid white;box-shadow:0 0 10px rgba(0,212,170,0.5);"></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

const hotspotIcon = new L.DivIcon({
  className: "",
  html: `<div style="width:12px;height:12px;background:#7c3aed;border-radius:50%;border:2px solid white;box-shadow:0 0 6px rgba(124,58,237,0.4);"></div>`,
  iconSize: [12, 12],
  iconAnchor: [6, 6],
});

// BRACU campus hotspots
const HOTSPOTS = [
  { name: "Gate 1", lat: 23.7794, lng: 90.4046 },
  { name: "Gate 2", lat: 23.7768, lng: 90.4052 },
  { name: "Library", lat: 23.7783, lng: 90.4038 },
  { name: "Cafeteria", lat: 23.7778, lng: 90.4048 },
  { name: "UB Building", lat: 23.7786, lng: 90.4044 },
  { name: "Residential", lat: 23.7772, lng: 90.4032 },
];

function MapUpdater({ center, follow, onInteract }: { center: { lat: number; lng: number }; follow: boolean; onInteract: () => void }) {
  const map = useMap();

  // Only auto-follow when the user hasn't dragged the map (fix: map used to
  // re-center on every GPS tick, making manual exploration impossible).
  useEffect(() => {
    if (!follow) return;
    map.setView([center.lat, center.lng], map.getZoom(), { animate: true });
  }, [center, follow, map]);

  useEffect(() => {
    const onDragStart = () => onInteract();
    map.on("dragstart", onDragStart);
    return () => { map.off("dragstart", onDragStart); };
  }, [map, onInteract]);

  return null;
}

interface Props {
  center: { lat: number; lng: number };
  points: Array<{ lat: number; lng: number; created_at: string }>;
  currentPos: { lat: number; lng: number } | null;
  isTracking: boolean;
}

export default function TrackingMap({ center, points, currentPos, isTracking }: Props) {
  const routeLine = points.map(p => [p.lat, p.lng] as [number, number]);
  const [follow, setFollow] = useState(true);

  return (
    <div className="map-container">
      <MapContainer
        center={[center.lat, center.lng]}
        zoom={16}
        style={{ height: "100%", width: "100%", background: "#0c1022" }}
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        <MapUpdater center={center} follow={follow} onInteract={() => setFollow(false)} />

        {/* Current position marker */}
        {currentPos && (
          <>
            <Marker position={[currentPos.lat, currentPos.lng]} icon={userIcon}>
              <Popup>
                <div style={{ color: "#000", fontSize: "0.85rem" }}>
                  <strong>📍 Your Location</strong><br />
                  {currentPos.lat.toFixed(5)}, {currentPos.lng.toFixed(5)}
                </div>
              </Popup>
            </Marker>
            {isTracking && (
              <Circle
                center={[currentPos.lat, currentPos.lng]}
                radius={50}
                pathOptions={{ color: "#00d4aa", fillColor: "#00d4aa", fillOpacity: 0.1, weight: 1 }}
              />
            )}
          </>
        )}

        {/* Route trail */}
        {routeLine.length > 1 && (
          <Polyline
            positions={routeLine}
            pathOptions={{ color: "#00d4aa", weight: 3, opacity: 0.7, dashArray: "5,10" }}
          />
        )}

        {/* Campus hotspots */}
        {HOTSPOTS.map((h) => (
          <Marker key={h.name} position={[h.lat, h.lng]} icon={hotspotIcon}>
            <Popup>
              <div style={{ color: "#000", fontSize: "0.85rem" }}>
                <strong>🏫 {h.name}</strong>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* Re-center control — appears once the user pans away from auto-follow */}
      {!follow && (
        <button
          onClick={() => setFollow(true)}
          style={{
            position: "absolute",
            right: 12,
            bottom: 24,
            zIndex: 1000,
            padding: "8px 14px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--surface-border)",
            background: "var(--surface)",
            color: "var(--text-primary)",
            fontSize: "0.8rem",
            fontWeight: 600,
            cursor: "pointer",
            boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
          }}
        >
          🎯 Re-center
        </button>
      )}
    </div>
  );
}

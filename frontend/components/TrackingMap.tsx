"use client";
import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap, Circle } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Dynamic marker creators for categorized hotspots
const createDivIcon = (color: string, ringColor: string, size = 14) => {
  return new L.DivIcon({
    className: "",
    html: `<div style="width:${size}px;height:${size}px;background:${color};border-radius:50%;border:2px solid ${ringColor};box-shadow:0 0 8px ${color}88;transition:transform 0.2s ease;"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
};

const userIcon = new L.DivIcon({
  className: "",
  html: `<div style="width:20px;height:20px;background:var(--primary,#00d4aa);border-radius:50%;border:3px solid white;box-shadow:0 0 12px rgba(0,212,170,0.6);animation:pulse 2s infinite;"></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

const categoryIcons: Record<string, L.DivIcon> = {
  campus_gate: createDivIcon("#10b981", "#ffffff", 14),
  academic: createDivIcon("#8b5cf6", "#ffffff", 14),
  transit_hub: createDivIcon("#06b6d4", "#ffffff", 14),
  residential: createDivIcon("#f59e0b", "#ffffff", 14),
  default: createDivIcon("#6366f1", "#ffffff", 12),
};

export interface HotspotItem {
  id: string;
  name: string;
  category: string;
  lat: number;
  lng: number;
  description?: string;
  popular?: boolean;
}

const DEFAULT_HOTSPOTS: HotspotItem[] = [
  { id: "gate 1", name: "Gate 1 (Main Entrance)", category: "campus_gate", lat: 23.7800, lng: 90.4100, description: "BRACU Main Gate 1 & Security Checkpoint", popular: true },
  { id: "gate 2", name: "Gate 2 (West Wing)", category: "campus_gate", lat: 23.7765, lng: 90.4070, description: "West Gate pickup area near cafeteria" },
  { id: "gate 3", name: "Gate 3 (East Wing)", category: "campus_gate", lat: 23.7792, lng: 90.4120, description: "East Gate & Bike Parking zone" },
  { id: "library", name: "Ayesha Abed Library", category: "academic", lat: 23.7781, lng: 90.4042, description: "Central Library & Study Plaza", popular: true },
  { id: "cafeteria", name: "Main Cafeteria & Lounge", category: "academic", lat: 23.7770, lng: 90.4050, description: "Cafeteria outdoor plaza", popular: true },
  { id: "ub building", name: "UB Building (UB01-UB07)", category: "academic", lat: 23.7788, lng: 90.4060, description: "University Building classrooms & labs", popular: true },
  { id: "residential", name: "Residential Campus Hub", category: "residential", lat: 23.7820, lng: 90.4080, description: "Student dormitories and housing area" },
  { id: "mohakhali", name: "Mohakhali Wireless Gate", category: "transit_hub", lat: 23.7700, lng: 90.4020, description: "Major transit point connecting to BRACU", popular: true },
  { id: "banani", name: "Banani Road 11 / Station", category: "transit_hub", lat: 23.7760, lng: 90.4100, description: "Banani commercial and pickup zone", popular: true },
  { id: "gulshan", name: "Gulshan-1 Circle", category: "transit_hub", lat: 23.7900, lng: 90.4100, description: "Gulshan roundabout & bus stoppage", popular: true },
  { id: "dhanmondi", name: "Dhanmondi Hub (Road 27)", category: "transit_hub", lat: 23.7450, lng: 90.3800, description: "Dhanmondi student carpool hub" },
  { id: "mirpur", name: "Mirpur 10 Circle (Metro)", category: "transit_hub", lat: 23.8100, lng: 90.3500, description: "Mirpur metro rail & student transit hub" },
];

function MapUpdater({ center, follow, onInteract }: { center: { lat: number; lng: number }; follow: boolean; onInteract: () => void }) {
  const map = useMap();

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
  hotspots?: HotspotItem[];
  onSelectHotspot?: (hotspot: HotspotItem) => void;
}

export default function TrackingMap({
  center,
  points,
  currentPos,
  isTracking,
  hotspots = DEFAULT_HOTSPOTS,
  onSelectHotspot
}: Props) {
  const routeLine = points.map(p => [p.lat, p.lng] as [number, number]);
  const [follow, setFollow] = useState(true);

  return (
    <div className="map-container" style={{ position: "relative", width: "100%", height: "100%", minHeight: 380, borderRadius: "var(--radius-md)", overflow: "hidden" }}>
      <MapContainer
        center={[center.lat, center.lng]}
        zoom={15}
        style={{ height: "100%", width: "100%", minHeight: 380, background: "#0c1022" }}
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
                <div style={{ color: "#0f172a", fontSize: "0.85rem", padding: "4px 0" }}>
                  <strong style={{ color: "#0284c7" }}>📍 Current Live Location</strong><br />
                  <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                    Lat: {currentPos.lat.toFixed(5)}, Lng: {currentPos.lng.toFixed(5)}
                  </span>
                </div>
              </Popup>
            </Marker>
            {isTracking && (
              <Circle
                center={[currentPos.lat, currentPos.lng]}
                radius={60}
                pathOptions={{ color: "#00d4aa", fillColor: "#00d4aa", fillOpacity: 0.15, weight: 1 }}
              />
            )}
          </>
        )}

        {/* Route trail */}
        {routeLine.length > 1 && (
          <Polyline
            positions={routeLine}
            pathOptions={{ color: "#00d4aa", weight: 3, opacity: 0.85, dashArray: "6,8" }}
          />
        )}

        {/* Categorized Campus Hotspots */}
        {hotspots.map((h) => {
          const icon = categoryIcons[h.category] || categoryIcons.default;
          return (
            <Marker key={h.id || h.name} position={[h.lat, h.lng]} icon={icon}>
              <Popup>
                <div style={{ color: "#0f172a", fontSize: "0.85rem", minWidth: 160 }}>
                  <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "#0f172a", marginBottom: 2 }}>
                    📍 {h.name}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: 6 }}>
                    {h.description || `Category: ${h.category?.replace("_", " ")}`}
                  </div>
                  {onSelectHotspot && (
                    <button
                      onClick={() => onSelectHotspot(h)}
                      style={{
                        background: "#00d4aa",
                        border: "none",
                        color: "#031b14",
                        padding: "4px 10px",
                        borderRadius: 4,
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        cursor: "pointer",
                        width: "100%",
                      }}
                    >
                      Use in Ride Filter
                    </button>
                  )}
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      {/* Map Legend */}
      <div style={{
        position: "absolute",
        left: 12,
        bottom: 12,
        zIndex: 1000,
        padding: "6px 12px",
        borderRadius: "var(--radius-md)",
        background: "rgba(12, 16, 34, 0.85)",
        backdropFilter: "blur(8px)",
        border: "1px solid rgba(255,255,255,0.1)",
        fontSize: "0.75rem",
        display: "flex",
        gap: 12,
        alignItems: "center",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981", display: "inline-block" }}></span> Gates
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#8b5cf6", display: "inline-block" }}></span> Academic
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#06b6d4", display: "inline-block" }}></span> Transit Hub
        </div>
      </div>

      {/* Re-center control */}
      {!follow && (
        <button
          onClick={() => setFollow(true)}
          style={{
            position: "absolute",
            right: 12,
            bottom: 12,
            zIndex: 1000,
            padding: "6px 14px",
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


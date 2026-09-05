"use client";
import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { API } from "@/lib/api";

interface Hotspot {
  id: string;
  name: string;
  category: string;
  lat: number;
  lng: number;
  description?: string;
  popular?: boolean;
}

// The API returns each stop as an object ({place, sequence, status}); the
// create-ride form and some older paths use plain strings. Accept either, so a
// multi-stop ride does not crash the page.
type RideStop = string | { place?: string; stop_name?: string; name?: string; id?: string };

const stopPlace = (stop: RideStop): string =>
  typeof stop === "string" ? stop : (stop?.place ?? stop?.stop_name ?? stop?.name ?? stop?.id ?? "");

// Feature 18: what cancelling would cost, previewed before anything happens.
interface CancelQuote {
  will_be_charged: boolean;
  penalty: number;
  exposure: number;
  dispatched: boolean;
  role: "driver" | "passenger";
  reason: string;
  wallet_balance: number;
  policy: { free_before_dispatch: boolean; penalty_rate: number; min_penalty: number; max_penalty: number };
}

// The driver's view of who has asked for a seat. `id` is the ride_passengers
// row id, which is what POST /rides/{id}/accept/{passenger_id} expects.
interface RidePassenger {
  id: string;
  passenger_id: string;
  passenger_name: string;
  seats: number;
  pickup_stop: string;
  dropoff_stop: string;
  status: string;
}

interface StopInfo {
  id: string;
  stop_name: string;
  stop_order: number;
  status: "pending" | "reached" | "departed";
  reached_at?: string | null;
}

interface RideInfo {
  id: string;
  driver_id: string;
  driver_name: string;
  driver_gender?: string;
  source: string;
  destination: string;
  status: string;
  distance_km: number | null;
  base_fare: number;
  surge_multiplier: number;
  total_seats: number;
  available_seats?: number;
  scheduled_at?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  created_at?: string | null;
  female_only?: boolean;
  stops?: RideStop[];
  stop_details?: StopInfo[];
}

interface MatchResult {
  ride: RideInfo;
  match_score: number;
  score_percentage: number;
  reasons: string[];
  pickup_distance_km: number;
  dropoff_distance_km: number;
  time_difference_mins: number | null;
}

interface SurgeInfo {
  hour: number;
  demand: number;
  active_rides: number;
  multiplier: number;
  label: string;
  message: string;
}

interface SurgeHour {
  hour: number;
  demand: number;
  multiplier: number;
  label: string;
  is_current: boolean;
}

interface SplitInfo {
  ride_id: string;
  source: string;
  destination: string;
  base_fare: number;
  surge_multiplier: number;
  total: number;
  total_seats: number;
  passenger_count: number;
  per_seat: number | null;
  breakdown: { passenger: string; seats: number; share: number; pickup_stop?: string; dropoff_stop?: string }[];
}

interface MeInfo {
  id: string;
  name?: string;
  role?: string;
  gender?: string;
}

const BADGES: Record<string, string> = {
  Peak: "badge-danger",
  High: "badge-warning",
  Elevated: "badge-info",
  Normal: "badge-success",
};

const CLASS_SCHEDULES = [
  { label: "08:00 AM Class", time: "08:00" },
  { label: "09:30 AM Class", time: "09:30" },
  { label: "11:00 AM Class", time: "11:00" },
  { label: "02:00 PM Class", time: "14:00" },
  { label: "03:30 PM Class", time: "15:30" },
  { label: "05:00 PM Return", time: "17:00" },
];

export default function RidesPage() {
  const [activeTab, setActiveTab] = useState<"browse" | "match" | "offer">("browse");
  const [filterType, setFilterType] = useState<"all" | "female" | "scheduled">("all");
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [surge, setSurge] = useState<SurgeInfo | null>(null);
  const [schedule, setSchedule] = useState<SurgeHour[]>([]);
  const [rides, setRides] = useState<{ mine: RideInfo[]; available: RideInfo[] }>({ mine: [], available: [] });
  const [form, setForm] = useState({
    source: "",
    destination: "",
    base_fare: "",
    total_seats: "4",
    scheduled_at: "",
    female_only: false,
    stops: [] as string[],
  });

  // Smart Matching State
  const [matchPickup, setMatchPickup] = useState("");
  const [matchDropoff, setMatchDropoff] = useState("");
  const [matchClassTime, setMatchClassTime] = useState("");
  const [matchFemaleOnly, setMatchFemaleOnly] = useState(false);
  const [matchResults, setMatchResults] = useState<MatchResult[]>([]);
  const [matchingLoading, setMatchingLoading] = useState(false);
  const [matchSearched, setMatchSearched] = useState(false);

  // Multi-Stop Join Modal State
  const [joiningRide, setJoiningRide] = useState<RideInfo | null>(null);
  const [joinPickupStop, setJoinPickupStop] = useState("");
  const [joinDropoffStop, setJoinDropoffStop] = useState("");
  const [joinSeats, setJoinSeats] = useState(1);
  const [bookingRide, setBookingRide] = useState(false);

  const [split, setSplit] = useState<Record<string, SplitInfo>>({});
  // Feature 18: Ride Cancellation Policy & Penalty
  const [cancelTarget, setCancelTarget] = useState<RideInfo | null>(null);
  const [cancelQuote, setCancelQuote] = useState<CancelQuote | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelling, setCancelling] = useState(false);
  // Ride lifecycle: accept requests, start the ride, end it (which settles the fare)
  const [manageOpen, setManageOpen] = useState<Record<string, RidePassenger[]>>({});
  const [busyRide, setBusyRide] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const [me, setMe] = useState<MeInfo | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const t = localStorage.getItem("token");
    setToken(t);
    const raw = localStorage.getItem("user");
    if (raw) {
      try {
        setMe(JSON.parse(raw) as MeInfo);
      } catch {
        // ignore
      }
    }
  }, []);

  const showNotice = (type: "success" | "error", text: string) => {
    setNotice({ type, text });
    setTimeout(() => setNotice(null), 5000);
  };

  const reload = useCallback(async () => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    try {
      const [s, sc, r, h] = await Promise.all([
        fetch(`${API}/surge/current`, { headers }).then(res => res.json()).catch(() => null),
        fetch(`${API}/surge/schedule`, { headers }).then(res => res.json()).then(d => d?.schedule ?? []).catch(() => []),
        fetch(`${API}/rides`, { headers }).then(res => res.json()).catch(() => ({ mine: [], available: [] })),
        fetch(`${API}/rides/hotspots`, { headers }).then(res => res.json()).catch(() => []),
      ]);
      setSurge(s);
      setSchedule(sc);
      setRides(r);
      setHotspots(h);
    } catch (err) {
      console.error("Error loading ride data", err);
    }
  }, [token]);

  useEffect(() => {
    reload();
  }, [reload]);

  const handleSmartMatch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!token || !matchPickup || !matchDropoff) {
      showNotice("error", "Please select both pickup and destination hotspots for smart matching");
      return;
    }
    setMatchingLoading(true);
    setMatchSearched(true);
    try {
      let url = `${API}/rides/match?pickup=${encodeURIComponent(matchPickup)}&dropoff=${encodeURIComponent(matchDropoff)}`;
      if (matchClassTime) {
        url += `&class_time=${encodeURIComponent(matchClassTime)}`;
      }
      if (matchFemaleOnly) {
        url += `&female_only=true`;
      }
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      });
      const data = await res.json();
      if (res.ok) {
        const rawList = Array.isArray(data) ? data : (data.matches || []);
        const normalized: MatchResult[] = rawList.map((item: any) => {
          if (item.ride) {
            return {
              ride: item.ride,
              match_score: item.match_score || item.score_percentage || 100,
              score_percentage: item.score_percentage || item.match_score || 100,
              reasons: item.reasons || item.match_reasons || [],
              pickup_distance_km: item.pickup_distance_km || 0,
              dropoff_distance_km: item.dropoff_distance_km || 0,
              time_difference_mins: item.time_difference_mins ?? null,
            };
          }
          return {
            ride: {
              id: item.id,
              driver_id: item.driver_id,
              driver_name: item.driver_name,
              source: item.source,
              destination: item.destination,
              status: item.status,
              distance_km: item.distance_km,
              base_fare: item.base_fare,
              surge_multiplier: item.surge_multiplier,
              total_seats: item.total_seats,
              available_seats: item.available_seats,
              scheduled_at: item.scheduled_at,
              female_only: item.female_only,
              stops: item.stops,
            },
            match_score: item.match_score || 100,
            score_percentage: item.match_score || 100,
            reasons: item.match_reasons || item.reasons || [],
            pickup_distance_km: 0,
            dropoff_distance_km: 0,
            time_difference_mins: null,
          };
        });
        setMatchResults(normalized);
      } else {
        showNotice("error", data.detail || "Failed to find smart matches");
        setMatchResults([]);
      }
    } catch (err) {
      showNotice("error", "Network error during smart matching");
      console.error(err);
    } finally {
      setMatchingLoading(false);
    }
  };

  const createRide = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    setLoading(true);
    try {
      const res = await fetch(`${API}/rides`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          source: form.source,
          destination: form.destination,
          base_fare: Number(form.base_fare),
          total_seats: Number(form.total_seats),
          scheduled_at: form.scheduled_at ? new Date(form.scheduled_at).toISOString() : undefined,
          female_only: form.female_only,
          stops: form.stops.filter(s => s.trim() !== ""),
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setForm({ source: "", destination: "", base_fare: "", total_seats: "4", scheduled_at: "", female_only: false, stops: [] });
        showNotice("success", data.message || "Ride offered successfully");
        reload();
        setActiveTab("browse");
      } else {
        showNotice("error", data.detail || "Failed to create ride");
      }
    } catch (err) {
      showNotice("error", "Network error — could not create ride");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const openJoinModal = (ride: RideInfo) => {
    setJoiningRide(ride);
    setJoinPickupStop(ride.source);
    setJoinDropoffStop(ride.destination);
    setJoinSeats(1);
  };

  const executeJoinRide = async () => {
    if (!token || !joiningRide || bookingRide) return;
    const availableSeats = joiningRide.available_seats ?? joiningRide.total_seats;
    if (availableSeats < 1) {
      showNotice("error", "This carpool is already full.");
      setJoiningRide(null);
      return;
    }
    if (!Number.isInteger(joinSeats) || joinSeats < 1 || joinSeats > availableSeats) {
      showNotice("error", `Choose between 1 and ${availableSeats} available seat${availableSeats === 1 ? "" : "s"}.`);
      return;
    }
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    setBookingRide(true);
    try {
      const res = await fetch(`${API}/rides/${joiningRide.id}/join`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          seats: joinSeats,
          pickup_stop: joinPickupStop || undefined,
          dropoff_stop: joinDropoffStop || undefined,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        showNotice(
          "success",
          data.requires_topup
            ? `Seat requested. Add ৳${data.topup_amount} to your wallet before the ride ends.`
            : (data.message || "Seat requested successfully!")
        );
        setJoiningRide(null);
        reload();
      } else {
        showNotice("error", data.detail || "Failed to join ride");
      }
    } catch (err) {
      showNotice("error", "Network error — could not join ride");
      console.error(err);
    } finally {
      setBookingRide(false);
    }
  };

  const updateStopStatus = async (rideId: string, stopId: string, status: "reached" | "departed") => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    try {
      const res = await fetch(`${API}/rides/${rideId}/stops/${stopId}/status`, {
        method: "PUT",
        headers,
        body: JSON.stringify({ status }),
      });
      const data = await res.json();
      if (res.ok) {
        showNotice("success", `Stop marked as ${status}`);
        reload();
      } else {
        showNotice("error", data.detail || "Failed to update stop status");
      }
    } catch (err) {
      showNotice("error", "Network error updating stop status");
      console.error(err);
    }
  };

  // ---- Ride lifecycle -------------------------------------------------------
  const authHeaders = () => ({
    Authorization: `Bearer ${localStorage.getItem("token")}`,
    "Content-Type": "application/json",
  });

  const toggleManage = async (rideId: string) => {
    if (manageOpen[rideId]) {
      setManageOpen(prev => {
        const next = { ...prev };
        delete next[rideId];
        return next;
      });
      return;
    }
    try {
      const res = await fetch(`${API}/rides/${rideId}`, { headers: authHeaders() });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not load the ride");
      setManageOpen(prev => ({ ...prev, [rideId]: data.passengers || [] }));
    } catch (e) {
      showNotice("error", e instanceof Error ? e.message : String(e));
    }
  };

  const acceptPassenger = async (rideId: string, passengerRowId: string, name: string) => {
    setBusyRide(rideId);
    try {
      const res = await fetch(`${API}/rides/${rideId}/accept/${passengerRowId}`, {
        method: "POST", headers: authHeaders(),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not accept the request");
      showNotice("success", `${name} is on board`);
      const refreshed = await fetch(`${API}/rides/${rideId}`, { headers: authHeaders() });
      const rd = await refreshed.json();
      setManageOpen(prev => ({ ...prev, [rideId]: rd.passengers || [] }));
      reload();
    } catch (e) {
      showNotice("error", e instanceof Error ? e.message : String(e));
    } finally {
      setBusyRide(null);
    }
  };

  // Ending a ride is what settles the fare: riders are debited, the driver is
  // credited, and the trip becomes a receipt.
  const lifecycleAction = async (rideId: string, action: "start" | "end") => {
    setBusyRide(rideId);
    try {
      const res = await fetch(`${API}/rides/${rideId}/${action}`, {
        method: "POST",
        headers: authHeaders(),
        body: action === "end" ? JSON.stringify({}) : undefined,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Could not ${action} the ride`);
      if (action === "end") {
        const st = data.settlement || {};
        const paid = st.driver_credited || 0;
        showNotice(
          "success",
          paid > 0
            ? `Ride completed — ৳${paid.toFixed(2)} paid into your wallet.`
            : "Ride completed."
        );
      } else {
        showNotice("success", "Ride started — you can now end it when you arrive.");
      }
      setManageOpen(prev => {
        const next = { ...prev };
        delete next[rideId];
        return next;
      });
      reload();
    } catch (e) {
      showNotice("error", e instanceof Error ? e.message : String(e));
    } finally {
      setBusyRide(null);
    }
  };

  // Fetch the penalty preview BEFORE opening the dialog, so the warning shows the
  // same number that will actually be charged.
  const openCancelModal = async (ride: RideInfo) => {
    const token = localStorage.getItem("token");
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    setCancelTarget(ride);
    setCancelQuote(null);
    setCancelReason("");
    try {
      const res = await fetch(`${API}/rides/${ride.id}/cancellation-policy`, { headers });
      const data = await res.json();
      if (res.ok) {
        setCancelQuote(data);
      } else {
        showNotice("error", data.detail || "Could not check the cancellation policy");
        setCancelTarget(null);
      }
    } catch {
      showNotice("error", "Network error - could not check the cancellation policy");
      setCancelTarget(null);
    }
  };

  const confirmCancel = async () => {
    if (!cancelTarget) return;
    const token = localStorage.getItem("token");
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    setCancelling(true);
    try {
      const res = await fetch(`${API}/rides/${cancelTarget.id}/cancel`, {
        method: "POST",
        headers,
        body: JSON.stringify({ reason: cancelReason }),
      });
      const data = await res.json();
      if (res.ok) {
        showNotice(data.penalty_charged > 0 || data.uncollected ? "error" : "success", data.message);
        setCancelTarget(null);
        setCancelQuote(null);
        reload();
      } else {
        showNotice("error", data.detail || "Could not cancel the ride");
      }
    } catch {
      showNotice("error", "Network error - could not cancel the ride");
    } finally {
      setCancelling(false);
    }
  };

  const loadSplit = async (rideId: string) => {
    if (split[rideId]) {
      setSplit({});
      return;
    }
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
    try {
      const res = await fetch(`${API}/rides/${rideId}/split`, { headers });
      const data = await res.json();
      if (!res.ok) {
        showNotice("error", data.detail || "Could not load fare split");
        return;
      }
      setSplit({ [rideId]: data });
    } catch (err) {
      showNotice("error", "Network error — could not load fare split");
      console.error(err);
    }
  };

  const getHotspotName = (idOrName: RideStop) => {
    const name = stopPlace(idOrName);
    if (!name) return "";
    const found = hotspots.find(
      h => h.id.toLowerCase() === name.toLowerCase() || h.name.toLowerCase() === name.toLowerCase()
    );
    return found ? found.name : name;
  };

  const surgeBadge = surge ? BADGES[surge.label] || "badge-success" : "badge-success";

  const upcomingPeaks = schedule
    .filter(h => h.hour > (surge?.hour ?? -1))
    .slice(0, 6)
    .filter(h => h.multiplier >= 1.3);

  const filteredAvailableRides = rides.available.filter(ride => {
    if (filterType === "female") return ride.female_only;
    if (filterType === "scheduled") return !!ride.scheduled_at;
    return true;
  });

  const renderRideCard = (ride: RideInfo, mine: boolean) => {
    const s = split[ride.id];
    const isDriver = me && ride.driver_id === me.id;
    const isParticipant = mine || isDriver;
    const chatOpen = isParticipant && (ride.status === "active" || ride.status === "scheduled");

    return (
      <div
        key={ride.id}
        className="glass-card"
        style={{
          padding: 20,
          border: ride.female_only ? "1px solid rgba(236, 72, 153, 0.4)" : undefined,
          background: ride.female_only ? "linear-gradient(135deg, rgba(236, 72, 153, 0.05), rgba(15, 23, 42, 0.8))" : undefined,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
          <div>
            {/* Route path with Stops */}
            <div style={{ fontWeight: 700, fontSize: "1.05rem", color: "var(--text-primary)", display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
              <span>📍 {getHotspotName(ride.source)}</span>
              {ride.stops && ride.stops.length > 0 && ride.stops.map((stop, idx) => (
                <span key={idx} style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                  ➜ <span style={{ color: "#a78bfa" }}>{getHotspotName(stop)}</span>
                </span>
              ))}
              <span>➜ 🏁 {getHotspotName(ride.destination)}</span>
            </div>

            <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginTop: 6, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
              <span>👤 Driver: <strong>{ride.driver_name}</strong></span>
              <span>🚘 {ride.total_seats} total seats</span>
              {ride.distance_km && <span>📏 est. {ride.distance_km} km</span>}
            </div>

            {ride.scheduled_at && (
              <div style={{ fontSize: "0.82rem", color: "var(--primary)", marginTop: 6, display: "flex", alignItems: "center", gap: 6 }}>
                <span>📅 Scheduled:</span>
                <strong>{new Date(ride.scheduled_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</strong>
              </div>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
            {ride.female_only && (
              <span className="badge" style={{ background: "rgba(236, 72, 153, 0.2)", color: "#f472b6", border: "1px solid rgba(236, 72, 153, 0.4)" }}>
                🌸 Female-Only
              </span>
            )}
            <span className={`badge ${ride.status === "completed" ? "badge-success" : ride.status === "active" ? "badge-info" : "badge-warning"}`}>
              {ride.status}
            </span>
            {ride.surge_multiplier > 1 && (
              <span className="badge badge-danger">⚡ Surge ×{ride.surge_multiplier}</span>
            )}
          </div>
        </div>

        {/* Multi-Stop Real-Time Status Progress (Driver View for active rides) */}
        {isDriver && ride.stop_details && ride.stop_details.length > 0 && (
          <div style={{ margin: "14px 0", padding: "12px 16px", background: "rgba(0,0,0,0.25)", borderRadius: "var(--radius-md)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <div style={{ fontSize: "0.85rem", fontWeight: 700, marginBottom: 8, color: "#38bdf8" }}>
              🚏 Route Waypoints & Stop Tracking
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {ride.stop_details.map(stop => (
                <div key={stop.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.82rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{
                      width: 10,
                      height: 10,
                      borderRadius: "50%",
                      background: stop.status === "departed" ? "#10b981" : stop.status === "reached" ? "#f59e0b" : "#64748b",
                    }} />
                    <span style={{ fontWeight: 600 }}>{stop.stop_order}. {getHotspotName(stop.stop_name)}</span>
                    <span className="badge" style={{ fontSize: "0.7rem", padding: "2px 6px" }}>{stop.status}</span>
                  </div>
                  {ride.status === "active" && (
                    <div style={{ display: "flex", gap: 6 }}>
                      {stop.status === "pending" && (
                        <button
                          className="btn btn-sm"
                          style={{ padding: "2px 8px", fontSize: "0.75rem", background: "var(--warning)", color: "#000" }}
                          onClick={() => updateStopStatus(ride.id, stop.id, "reached")}
                        >
                          Mark Reached
                        </button>
                      )}
                      {stop.status === "reached" && (
                        <button
                          className="btn btn-sm"
                          style={{ padding: "2px 8px", fontSize: "0.75rem", background: "var(--success)", color: "#000" }}
                          onClick={() => updateStopStatus(ride.id, stop.id, "departed")}
                        >
                          Mark Departed
                        </button>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ fontSize: "0.95rem", color: "var(--text-secondary)", marginBottom: 14 }}>
          Base Fare: <strong style={{ color: "var(--text-primary)" }}>৳{ride.base_fare}</strong>
          {ride.surge_multiplier > 1 && (
            <span style={{ color: "var(--warning)", marginLeft: 8 }}>
              × {ride.surge_multiplier} = ৳{(ride.base_fare * ride.surge_multiplier).toFixed(2)}
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          {!mine && ride.status === "scheduled" && (
            ride.available_seats === 0 ? (
              <span className="badge badge-danger">Full</span>
            ) : (
              <button className="btn btn-sm btn-primary" onClick={() => openJoinModal(ride)}>
                🚕 Request Seat
              </button>
            )
          )}
          {/* Driver controls: accept requests, then start, then end (which pays out) */}
          {isDriver && ride.status !== "completed" && ride.status !== "cancelled" && (
            <button className="btn btn-sm btn-secondary" onClick={() => toggleManage(ride.id)}>
              👥 {manageOpen[ride.id] ? "Hide requests" : "Manage requests"}
            </button>
          )}
          {isDriver && ride.status === "scheduled" && (
            <button className="btn btn-sm btn-primary" disabled={busyRide === ride.id}
                    onClick={() => lifecycleAction(ride.id, "start")}>
              ▶ Start Ride
            </button>
          )}
          {isDriver && ride.status === "active" && (
            <button className="btn btn-sm btn-primary" disabled={busyRide === ride.id}
                    onClick={() => lifecycleAction(ride.id, "end")}>
              ⏹ End Ride &amp; Collect Fare
            </button>
          )}
          {isParticipant && (ride.status === "active" || ride.status === "completed") && (
            <button className="btn btn-sm btn-secondary" onClick={() => loadSplit(ride.id)}>
              💸 Fare Splitter
            </button>
          )}
          {chatOpen && (
            <Link href={`/dashboard/chat/${ride.id}`} className="btn btn-sm btn-secondary">
              💬 Ride Chat
            </Link>
          )}
          {isParticipant && (
            <Link href="/dashboard/track" className="btn btn-sm btn-secondary">
              🗺️ Live Map Tracking
            </Link>
          )}
          {/* Feature 18: only offered while the ride can still be cancelled */}
          {isParticipant && (ride.status === "scheduled" || ride.status === "active") && (
            <button className="btn btn-sm btn-danger" onClick={() => openCancelModal(ride)}>
              ✖ {isDriver ? "Cancel Ride" : "Cancel My Seat"}
            </button>
          )}
        </div>

        {manageOpen[ride.id] && (
          <div style={{ marginTop: 16, padding: 16, background: "var(--surface)",
                        borderRadius: "var(--radius-md)", border: "1px solid var(--surface-border)" }}>
            <div style={{ fontWeight: 700, marginBottom: 10, fontSize: "0.92rem" }}>
              👥 Seat requests
            </div>
            {manageOpen[ride.id].length === 0 ? (
              <p style={{ fontSize: "0.85rem", color: "var(--text-tertiary)" }}>
                Nobody has requested a seat yet.
              </p>
            ) : (
              manageOpen[ride.id].map(pp => (
                <div key={pp.id} style={{ display: "flex", justifyContent: "space-between",
                                          alignItems: "center", gap: 12, flexWrap: "wrap",
                                          padding: "8px 0",
                                          borderTop: "1px solid var(--surface-border)" }}>
                  <div style={{ fontSize: "0.85rem" }}>
                    <strong style={{ color: "var(--text-primary)" }}>{pp.passenger_name}</strong>
                    <span style={{ color: "var(--text-tertiary)" }}>
                      {" "}· {pp.seats} seat{pp.seats === 1 ? "" : "s"}
                      {pp.pickup_stop ? ` · ${getHotspotName(pp.pickup_stop)} → ${getHotspotName(pp.dropoff_stop)}` : ""}
                    </span>
                  </div>
                  {pp.status === "requested" ? (
                    <button className="btn btn-sm btn-primary" disabled={busyRide === ride.id}
                            onClick={() => acceptPassenger(ride.id, pp.id, pp.passenger_name)}>
                      ✓ Accept
                    </button>
                  ) : (
                    <span className={`badge ${pp.status === "cancelled" ? "badge-danger" : "badge-success"}`}>
                      {pp.status}
                    </span>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {s && (
          <div style={{ marginTop: 16, padding: 16, background: "var(--surface)", borderRadius: "var(--radius-md)", border: "1px solid var(--surface-border)" }}>
            <div style={{ fontWeight: 700, marginBottom: 8, display: "flex", justifyContent: "space-between" }}>
              <span>💸 Fair Campus Cost Split</span>
              <span style={{ color: "var(--primary)" }}>{s.passenger_count} Passenger(s)</span>
            </div>
            <div style={{ fontSize: "0.85rem", display: "grid", gap: 6, color: "var(--text-secondary)" }}>
              <div>Base fare: ৳{s.base_fare} {s.surge_multiplier > 1 ? `× surge ${s.surge_multiplier}` : ""}</div>
              <div>Total Ride Cost: <strong style={{ color: "var(--text-primary)" }}>৳{s.total}</strong></div>
              <div style={{ color: "var(--primary)", fontWeight: 700, fontSize: "1.05rem", marginTop: 4 }}>
                Estimated per seat: ৳{s.per_seat ?? "—"}
              </div>
            </div>
            {s.breakdown.length > 0 && (
              <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.06)", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Individual Passenger Shares:</div>
                {s.breakdown.map((b, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
                    <span>
                      • {b.passenger} {b.seats > 1 ? `(${b.seats} seats)` : ""}
                      {b.pickup_stop && b.dropoff_stop ? ` [${getHotspotName(b.pickup_stop)} ➜ ${getHotspotName(b.dropoff_stop)}]` : ""}
                    </span>
                    <strong style={{ color: "var(--text-primary)" }}>৳{b.share}</strong>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      <div className="page-header" style={{ marginBottom: 20 }}>
        <h1 className="page-title">🚗 BRACU Campus Rides</h1>
        <p className="page-subtitle">Smart matching · multi-stop carpools · female-only safe mode · advance class scheduling</p>
      </div>

      {notice && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: "var(--radius-md)",
            fontSize: "0.85rem",
            marginBottom: 20,
            background: notice.type === "success" ? "var(--success-muted)" : "var(--danger-muted)",
            color: notice.type === "success" ? "var(--success)" : "var(--danger)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span>{notice.text}</span>
          <button onClick={() => setNotice(null)} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer" }}>✕</button>
        </div>
      )}

      {/* Surge Indicator */}
      {surge && (
        <div className="glass-card" style={{ padding: 18, marginBottom: 20, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: "1.6rem" }}>⚡</span>
            <div>
              <div style={{ fontWeight: 700 }}>Peak Hour Surge Status</div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{surge.message}</div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className={`badge ${surgeBadge}`}>{surge.label}</span>
            <span style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--warning)" }}>×{surge.multiplier}</span>
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 24, borderBottom: "1px solid var(--surface-border)", paddingBottom: 12 }}>
        <button
          onClick={() => setActiveTab("browse")}
          className={`btn ${activeTab === "browse" ? "btn-primary" : "btn-secondary"}`}
          style={{ padding: "8px 18px", fontWeight: 600 }}
        >
          🔍 Browse Rides
        </button>
        <button
          onClick={() => setActiveTab("match")}
          className={`btn ${activeTab === "match" ? "btn-primary" : "btn-secondary"}`}
          style={{ padding: "8px 18px", fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}
        >
          <span>⚡ Smart Match</span>
          <span className="badge badge-info" style={{ fontSize: "0.65rem", padding: "1px 6px" }}>AI</span>
        </button>
        <button
          onClick={() => setActiveTab("offer")}
          className={`btn ${activeTab === "offer" ? "btn-primary" : "btn-secondary"}`}
          style={{ padding: "8px 18px", fontWeight: 600 }}
        >
          ➕ Offer Ride
        </button>
      </div>

      {/* TAB 1: SMART MATCHING */}
      {activeTab === "match" && (
        <div style={{ marginBottom: 32 }}>
          <div className="glass-card" style={{ padding: 24, marginBottom: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <span style={{ fontSize: "1.5rem" }}>🎯</span>
              <div>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700 }}>Campus Zone Smart Matcher</h3>
                <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                  Algorithmically matches your route, pickup gate, intermediate stops, and class timetable with available carpools.
                </p>
              </div>
            </div>

            <form onSubmit={handleSmartMatch} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
                <div className="input-group">
                  <label className="input-label">Pickup Hotspot (From)</label>
                  <select
                    className="input select"
                    required
                    value={matchPickup}
                    onChange={e => setMatchPickup(e.target.value)}
                  >
                    <option value="">Select pickup point</option>
                    {hotspots.map(h => (
                      <option key={h.id} value={h.id}>{h.name} ({h.category.replace("_", " ")})</option>
                    ))}
                  </select>
                </div>

                <div className="input-group">
                  <label className="input-label">Destination Hotspot (To)</label>
                  <select
                    className="input select"
                    required
                    value={matchDropoff}
                    onChange={e => setMatchDropoff(e.target.value)}
                  >
                    <option value="">Select destination</option>
                    {hotspots.map(h => (
                      <option key={h.id} value={h.id}>{h.name}</option>
                    ))}
                  </select>
                </div>

                <div className="input-group">
                  <label className="input-label">Target Class Time / Schedule</label>
                  <input
                    className="input"
                    type="time"
                    value={matchClassTime}
                    onChange={e => setMatchClassTime(e.target.value)}
                  />
                </div>
              </div>

              {/* Quick Class Presets */}
              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: 6 }}>Class Schedule Quick Presets:</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {CLASS_SCHEDULES.map(c => (
                    <button
                      key={c.time}
                      type="button"
                      onClick={() => setMatchClassTime(c.time)}
                      className="badge"
                      style={{
                        cursor: "pointer",
                        background: matchClassTime === c.time ? "var(--primary)" : "rgba(255,255,255,0.08)",
                        color: matchClassTime === c.time ? "#031b14" : "var(--text-primary)",
                        padding: "4px 10px",
                        border: "none",
                        fontSize: "0.75rem",
                      }}
                    >
                      🕒 {c.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Female Only Checkbox */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: "0.9rem", color: "#f472b6" }}>
                  <input
                    type="checkbox"
                    checked={matchFemaleOnly}
                    onChange={e => setMatchFemaleOnly(e.target.checked)}
                  />
                  <span>🌸 Show only Female-Only Verified Carpools</span>
                </label>

                <button type="submit" className="btn btn-primary" disabled={matchingLoading}>
                  {matchingLoading ? "Matching Routes..." : "🔍 Find Best Matches"}
                </button>
              </div>
            </form>
          </div>

          {/* Match Results */}
          {matchSearched && (
            <div>
              <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 12 }}>
                Smart Match Recommendations ({matchResults.length})
              </h3>
              {matchResults.length === 0 ? (
                <div className="glass-card" style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)" }}>
                  No compatible rides found matching this exact route and time. Try adjusting your time or pickup hotspot, or offer a new ride!
                </div>
              ) : (
                <div style={{ display: "grid", gap: 16 }}>
                  {matchResults.map((result, idx) => (
                    <div
                      key={idx}
                      className="glass-card"
                      style={{
                        padding: 20,
                        border: `1px solid ${result.score_percentage >= 80 ? "rgba(0, 212, 170, 0.5)" : "var(--surface-border)"}`,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span
                              className="badge"
                              style={{
                                background: result.score_percentage >= 80 ? "var(--success-muted)" : "var(--warning-muted)",
                                color: result.score_percentage >= 80 ? "var(--success)" : "var(--warning)",
                                fontWeight: 800,
                                fontSize: "0.85rem",
                              }}
                            >
                              ⚡ {result.score_percentage}% Match Score
                            </span>
                            {result.ride?.female_only && (
                              <span className="badge" style={{ background: "rgba(236, 72, 153, 0.2)", color: "#f472b6" }}>
                                🌸 Female-Only
                              </span>
                            )}
                          </div>
                          <div style={{ fontWeight: 700, fontSize: "1.1rem", marginTop: 8 }}>
                            📍 {getHotspotName(result.ride?.source || "")} ➜ 🏁 {getHotspotName(result.ride?.destination || "")}
                          </div>
                          <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: 4 }}>
                            Driver: <strong>{result.ride?.driver_name}</strong> · Base Fare: ৳{result.ride?.base_fare} · Available Seats: {result.ride?.total_seats}
                          </div>
                        </div>

                        <button className="btn btn-primary" onClick={() => result.ride && openJoinModal(result.ride)}>
                          🚕 Join Ride
                        </button>
                      </div>

                      {/* Matching Reasons Tags */}
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                        {(result.reasons || []).map((reason, rIdx) => (
                          <span key={rIdx} className="badge badge-info" style={{ fontSize: "0.75rem", textTransform: "none" }}>
                            ✓ {reason}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: OFFER A RIDE (DRIVER) */}
      {activeTab === "offer" && (
        <div className="glass-card" style={{ padding: 24, marginBottom: 32 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
            <span style={{ fontSize: "1.5rem" }}>🚘</span>
            <div>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700 }}>Offer a Campus Ride</h3>
              <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                Share your car or bike with fellow BRACU students. Add intermediate campus gates or transit stops to maximize carpool occupancy.
              </p>
            </div>
          </div>

          <form onSubmit={createRide} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
              <div className="input-group">
                <label className="input-label">Pickup Hotspot (From)</label>
                <select
                  className="input select"
                  required
                  value={form.source}
                  onChange={e => setForm({ ...form, source: e.target.value })}
                >
                  <option value="">Select pickup point</option>
                  {hotspots.map(h => (
                    <option key={h.id} value={h.id}>{h.name}</option>
                  ))}
                </select>
              </div>

              <div className="input-group">
                <label className="input-label">Destination Hotspot (To)</label>
                <select
                  className="input select"
                  required
                  value={form.destination}
                  onChange={e => setForm({ ...form, destination: e.target.value })}
                >
                  <option value="">Select destination</option>
                  {hotspots.map(h => (
                    <option key={h.id} value={h.id}>{h.name}</option>
                  ))}
                </select>
              </div>

              <div className="input-group">
                <label className="input-label">Base Fare (৳)</label>
                <input
                  className="input"
                  type="number"
                  min="10"
                  step="5"
                  required
                  placeholder="e.g. 100"
                  value={form.base_fare}
                  onChange={e => setForm({ ...form, base_fare: e.target.value })}
                />
              </div>

              <div className="input-group">
                <label className="input-label">Available Seats</label>
                <input
                  className="input"
                  type="number"
                  min="1"
                  max="10"
                  required
                  value={form.total_seats}
                  onChange={e => setForm({ ...form, total_seats: e.target.value })}
                />
              </div>
            </div>

            {/* Advance Scheduling & Female-Only Option */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16, alignItems: "center" }}>
              <div className="input-group">
                <label className="input-label">Schedule Advance Booking (Optional)</label>
                <input
                  className="input"
                  type="datetime-local"
                  value={form.scheduled_at}
                  onChange={e => setForm({ ...form, scheduled_at: e.target.value })}
                />
              </div>

              {me?.gender === "female" && (
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontWeight: 600, color: "#f472b6", paddingTop: 20 }}>
                  <input
                    type="checkbox"
                    checked={form.female_only}
                    onChange={e => setForm({ ...form, female_only: e.target.checked })}
                  />
                  <span>🌸 Female-Only Mode (Only female riders can view & join)</span>
                </label>
              )}
            </div>

            {/* Intermediate Multi-Stop Waypoints */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <label className="input-label" style={{ marginBottom: 0 }}>
                  Intermediate Campus Stops (Multi-Stop Support)
                </label>
                <button
                  type="button"
                  className="btn btn-sm btn-secondary"
                  onClick={() => setForm({ ...form, stops: [...form.stops, ""] })}
                >
                  + Add Stop
                </button>
              </div>

              {form.stops.length > 0 ? (
                <div style={{ display: "grid", gap: 8 }}>
                  {form.stops.map((stop, idx) => (
                    <div key={idx} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", width: 60 }}>Stop {idx + 1}:</span>
                      <select
                        className="input select"
                        style={{ flex: 1 }}
                        value={stop}
                        onChange={e => {
                          const updated = [...form.stops];
                          updated[idx] = e.target.value;
                          setForm({ ...form, stops: updated });
                        }}
                      >
                        <option value="">Select waypoint stop</option>
                        {hotspots.map(h => (
                          <option key={h.id} value={h.id}>{h.name}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: "6px 12px" }}
                        onClick={() => setForm({ ...form, stops: form.stops.filter((_, i) => i !== idx) })}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: "0.8rem", color: "var(--text-tertiary)" }}>
                  No intermediate stops added yet. Direct route from source to destination.
                </div>
              )}
            </div>

            <button type="submit" className="btn btn-primary" style={{ marginTop: 8 }} disabled={loading}>
              {loading ? "Publishing Ride..." : "Publish Ride Offer"}
            </button>
          </form>
        </div>
      )}

      {/* TAB 3: BROWSE RIDES */}
      {activeTab === "browse" && (
        <>
          {/* Quick Filter Bar */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={() => setFilterType("all")}
                className={`btn btn-sm ${filterType === "all" ? "btn-primary" : "btn-secondary"}`}
              >
                All Rides ({rides.available.length})
              </button>
              <button
                onClick={() => setFilterType("female")}
                className={`btn btn-sm ${filterType === "female" ? "btn-primary" : "btn-secondary"}`}
                style={{ color: filterType === "female" ? undefined : "#f472b6" }}
              >
                🌸 Female-Only
              </button>
              <button
                onClick={() => setFilterType("scheduled")}
                className={`btn btn-sm ${filterType === "scheduled" ? "btn-primary" : "btn-secondary"}`}
              >
                🕒 Scheduled Ahead
              </button>
            </div>

            <button onClick={reload} className="btn btn-sm btn-secondary">
              🔄 Refresh Live Rides
            </button>
          </div>

          {/* Upcoming peak strip */}
          {upcomingPeaks.length > 0 && (
            <div className="glass-card" style={{ padding: 14, marginBottom: 20 }}>
              <div style={{ fontWeight: 600, fontSize: "0.85rem", marginBottom: 8 }}>⏰ Upcoming BRACU Peak Windows</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {upcomingPeaks.map(h => (
                  <span key={h.hour} className={`badge ${h.multiplier >= 1.5 ? "badge-danger" : "badge-warning"}`} style={{ textTransform: "none" }}>
                    {h.hour.toString().padStart(2, "0")}:00 — ×{h.multiplier} {h.label}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* My Rides */}
          <h3 style={{ fontSize: "1.05rem", fontWeight: 700, marginBottom: 12 }}>My Active & Created Rides</h3>
          <div style={{ display: "grid", gap: 14, marginBottom: 32 }}>
            {rides.mine.length === 0 && (
              <div className="glass-card" style={{ padding: 18, color: "var(--text-tertiary)", fontSize: "0.9rem" }}>
                You haven&apos;t joined or created any active rides yet. Browse available campus rides below or offer one!
              </div>
            )}
            {rides.mine.map(r => renderRideCard(r, true))}
          </div>

          {/* Available Campus Rides grouped by Destination */}
          <h3 style={{ fontSize: "1.05rem", fontWeight: 700, marginBottom: 12 }}>Available Campus Carpools</h3>
          <div style={{ display: "grid", gap: 20 }}>
            {filteredAvailableRides.length === 0 && (
              <div className="glass-card" style={{ padding: 24, textAlign: "center", color: "var(--text-tertiary)", fontSize: "0.9rem" }}>
                No rides available matching the selected filter. Check back soon or switch to Smart Matching!
              </div>
            )}

            {Object.entries(
              filteredAvailableRides.reduce((acc, ride) => {
                const dest = ride.destination;
                if (!acc[dest]) acc[dest] = [];
                acc[dest].push(ride);
                return acc;
              }, {} as Record<string, RideInfo[]>)
            ).map(([dest, groupRides]) => (
              <div key={dest}>
                <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--primary)", marginBottom: 10, paddingBottom: 4, borderBottom: "1px solid var(--surface-border)" }}>
                  📍 Heading to {getHotspotName(dest)} ({groupRides.length} available)
                </div>
                <div style={{ display: "grid", gap: 12 }}>
                  {groupRides.map(r => renderRideCard(r, false))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Multi-Stop Join Modal */}
      {joiningRide && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          background: "rgba(0,0,0,0.7)",
          backdropFilter: "blur(4px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 9999,
          padding: 16,
        }}>
          <div className="glass-card" style={{ width: "100%", maxWidth: 480, padding: 24, background: "var(--surface)", border: "1px solid var(--primary)" }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 12 }}>
              🚕 Select Your Pickup & Drop-Off Stops
            </h3>
            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: 16 }}>
              This driver is making multiple stops. Choose where you would like to be picked up and dropped off along the route.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div className="input-group">
                <label className="input-label">Your Pickup Stop</label>
                <select
                  className="input select"
                  value={joinPickupStop}
                  onChange={e => setJoinPickupStop(e.target.value)}
                >
                  <option value={joiningRide.source}>Source: {getHotspotName(joiningRide.source)}</option>
                  {joiningRide.stops?.map((stop, idx) => (
                    <option key={idx} value={stopPlace(stop)}>Stop {idx + 1}: {getHotspotName(stop)}</option>
                  ))}
                </select>
              </div>

              <div className="input-group">
                <label className="input-label">Your Drop-Off Stop</label>
                <select
                  className="input select"
                  value={joinDropoffStop}
                  onChange={e => setJoinDropoffStop(e.target.value)}
                >
                  {joiningRide.stops?.map((stop, idx) => (
                    <option key={idx} value={stopPlace(stop)}>Stop {idx + 1}: {getHotspotName(stop)}</option>
                  ))}
                  <option value={joiningRide.destination}>Final: {getHotspotName(joiningRide.destination)}</option>
                </select>
              </div>

              <div className="input-group">
                <label className="input-label">Seats Required</label>
                <input
                  className="input"
                  type="number"
                  min="1"
                  max={joiningRide.available_seats ?? joiningRide.total_seats}
                  value={joinSeats}
                  onChange={e => setJoinSeats(Number(e.target.value))}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 10 }}>
                <button className="btn btn-secondary" onClick={() => setJoiningRide(null)}>
                  Cancel
                </button>
                <button className="btn btn-primary" onClick={executeJoinRide} disabled={bookingRide}>
                  {bookingRide ? "Requesting Seat..." : "Confirm & Request Seat"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Feature 18: Ride Cancellation Policy & Penalty - warn before charging */}
      {cancelTarget && (
        <div className="modal-backdrop" onClick={() => !cancelling && setCancelTarget(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 460 }}>
            <div className="modal-title">
              {cancelQuote?.role === "driver" ? "Cancel this ride?" : "Cancel your seat?"}
            </div>

            <div style={{ fontSize: "0.86rem", color: "var(--text-secondary)", marginBottom: 14 }}>
              {cancelTarget.source} to {cancelTarget.destination}
            </div>

            {!cancelQuote ? (
              <div style={{ display: "flex", justifyContent: "center", padding: 24 }}>
                <span className="spinner" />
              </div>
            ) : (
              <>
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "var(--radius-md)",
                    borderLeft: `3px solid ${cancelQuote.will_be_charged ? "var(--danger)" : "var(--success)"}`,
                    background: cancelQuote.will_be_charged ? "var(--danger-muted)" : "var(--success-muted)",
                    marginBottom: 14,
                  }}
                >
                  <div
                    style={{
                      fontWeight: 700,
                      fontSize: "0.9rem",
                      color: cancelQuote.will_be_charged ? "var(--danger)" : "var(--success)",
                      marginBottom: 4,
                    }}
                  >
                    {cancelQuote.will_be_charged
                      ? `⚠️ Late-cancellation fee: ৳${cancelQuote.penalty.toFixed(2)}`
                      : "✅ Free to cancel"}
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                    {cancelQuote.reason}
                  </div>
                </div>

                {cancelQuote.will_be_charged && (
                  <div style={{ fontSize: "0.76rem", color: "var(--text-tertiary)", marginBottom: 14, lineHeight: 1.7 }}>
                    Your share of this ride: ৳{cancelQuote.exposure.toFixed(2)} &middot; fee is{" "}
                    {Math.round(cancelQuote.policy.penalty_rate * 100)}% (min ৳
                    {cancelQuote.policy.min_penalty.toFixed(0)}, max ৳
                    {cancelQuote.policy.max_penalty.toFixed(0)}).
                    <br />
                    Wallet balance: ৳{cancelQuote.wallet_balance.toFixed(2)}
                    {cancelQuote.wallet_balance < cancelQuote.penalty && (
                      <span style={{ color: "var(--warning)" }}>
                        {" "}— not enough to cover the fee; it will be recorded as unpaid.
                      </span>
                    )}
                  </div>
                )}

                <div className="input-group">
                  <label className="input-label">Reason (optional)</label>
                  <input
                    className="input"
                    value={cancelReason}
                    onChange={e => setCancelReason(e.target.value)}
                    placeholder="e.g. class got cancelled"
                    maxLength={300}
                  />
                </div>

                <div className="modal-actions">
                  <button className="btn btn-ghost" disabled={cancelling} onClick={() => setCancelTarget(null)}>
                    Keep the ride
                  </button>
                  <button className="btn btn-danger" disabled={cancelling} onClick={confirmCancel}>
                    {cancelling ? (
                      <span className="spinner" />
                    ) : cancelQuote.will_be_charged ? (
                      `Cancel and pay ৳${cancelQuote.penalty.toFixed(2)}`
                    ) : (
                      "Yes, cancel"
                    )}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

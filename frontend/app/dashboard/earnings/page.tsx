"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { API } from "@/lib/api";

// Feature 16: Driver Earnings Dashboard
//
// Reads the wallet LEDGER, never a second computation over `rides` — the figure
// here and the figure in the wallet are the same number by construction.
//
// Chart notes: one series, so no legend (the heading names it). Fill is #00a888,
// a step of the brand teal chosen to sit inside the dark-mode lightness band
// (--primary #00d4aa is L0.775, too light for a fill on this surface). Values are
// direct-labelled only on the peak and the current week; everything else is on
// hover. A table toggle carries the same data for non-visual reading.

const SERIES = "#00a888";
const SERIES_HOVER = "#00c49c";

/** Round the axis up to a readable maximum so ticks land on 100/250/500 style
 *  numbers instead of max-times-a-fraction (350 -> 263 -> 175 -> 88). */
function niceAxisMax(max: number, intervals = 4): number {
  if (max <= 0) return 0;
  const rough = max / intervals;
  const exp = Math.pow(10, Math.floor(Math.log10(rough)));
  const frac = rough / exp;
  const niceFrac = frac <= 1 ? 1 : frac <= 2 ? 2 : frac <= 2.5 ? 2.5 : frac <= 5 ? 5 : 10;
  return niceFrac * exp * intervals;
}

interface Summary {
  total_earned: number;
  total_platform_fees: number;
  gross_earned: number;
  rides_paid: number;
  avg_per_ride: number;
  this_week: number;
  this_week_rides: number;
  last_week: number;
  change_pct: number;
  available_payout: number;
  total_distance_km: number;
  total_passengers: number;
  unsettled_rides: number;
  unsettled_value: number;
  fully_unpaid_rides: number;
  partially_paid_rides: number;
  week_starting: string;
}

interface Bucket {
  period_start: string;
  label: string;
  amount: number;
  rides: number;
  is_current: boolean;
}

interface Series { buckets: Bucket[]; max: number; total: number }

type Period = "day" | "week";

interface RideRow {
  ride_id: string;
  source: string;
  destination: string;
  when: string;
  distance_km: number | null;
  passengers: number;
  gross: number;
  platform_fee: number;
  net: number;
  settled: boolean;
  shortfall: number;
}

const taka = (n: number) =>
  "৳" + n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function StatTile({ label, value, sub, tone }: {
  label: string; value: string; sub?: string; tone?: "good" | "warn";
}) {
  const color =
    tone === "good" ? "var(--success)" : tone === "warn" ? "var(--warning)" : "var(--text-primary)";
  return (
    <div className="glass-card" style={{ padding: 20 }}>
      <div style={{ fontSize: "0.7rem", color: "var(--text-tertiary)", textTransform: "uppercase",
                    letterSpacing: "0.08em", fontWeight: 600, marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: "1.9rem", fontWeight: 800, color, lineHeight: 1.1 }}>{value}</div>
      {sub && (
        <div style={{ fontSize: "0.76rem", color: "var(--text-tertiary)", marginTop: 6 }}>{sub}</div>
      )}
    </div>
  );
}

export default function EarningsPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [weekly, setWeekly] = useState<Series>({ buckets: [], max: 0, total: 0 });
  const [daily, setDaily] = useState<Series>({ buckets: [], max: 0, total: 0 });
  const [period, setPeriod] = useState<Period>("week");
  const [rides, setRides] = useState<RideRow[]>([]);
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  const [error, setError] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token]
  );

  const fetchAll = useCallback(async () => {
    const [s, w, d, r] = await Promise.all([
      fetch(`${API}/earnings/summary`, { headers }).then(x => x.json()),
      fetch(`${API}/earnings/weekly?weeks=8`, { headers }).then(x => x.json()),
      fetch(`${API}/earnings/daily?days=14`, { headers }).then(x => x.json()),
      fetch(`${API}/earnings/rides?limit=25`, { headers }).then(x => x.json()),
    ]);
    const asSeries = (o: { buckets?: Bucket[]; max?: number; total?: number }): Series =>
      ({ buckets: o.buckets ?? [], max: o.max ?? 0, total: o.total ?? 0 });
    return {
      s: s as Summary,
      w: asSeries(w),
      d: asSeries(d),
      r: (Array.isArray(r) ? r : []) as RideRow[],
    };
  }, [headers]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchAll()
      .then(({ s, w, d, r }) => {
        if (cancelled) return;
        setSummary(s);
        setWeekly(w);
        setDaily(d);
        setRides(r);
      })
      .catch(() => { if (!cancelled) setError("Could not load your earnings."); });
    return () => { cancelled = true; };
  }, [token, fetchAll]);

  if (error) {
    return (
      <div className="glass-card" style={{ padding: 24, color: "var(--danger)" }}>⚠️ {error}</div>
    );
  }
  if (!summary) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 64 }}>
        <span className="spinner spinner-lg" />
      </div>
    );
  }

  const up = summary.change_pct >= 0;
  const hasEarnings = summary.rides_paid > 0;
  const active = period === "week" ? weekly : daily;
  const buckets = active.buckets;
  const maxBucket = active.max;
  const axisMax = niceAxisMax(maxBucket);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">💰 Driver Earnings</h1>
        <p className="page-subtitle">
          What your completed rides actually paid into your wallet.
        </p>
      </div>

      {/* Headline numbers — magnitude with no comparison needed, so tiles, not a chart */}
      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <StatTile
          label="Total Earned"
          value={taka(summary.total_earned)}
          sub={`${summary.rides_paid} paid ride${summary.rides_paid === 1 ? "" : "s"} · avg ${taka(summary.avg_per_ride)}`}
          tone="good"
        />
        <StatTile
          label="Ready to Cash Out"
          value={taka(summary.available_payout)}
          sub="Current wallet balance"
        />
        <StatTile
          label="This Week"
          value={taka(summary.this_week)}
          sub={
            summary.last_week > 0
              ? `${up ? "▲" : "▼"} ${Math.abs(summary.change_pct)}% vs last week (${taka(summary.last_week)})`
              : "No earnings last week"
          }
        />
        <StatTile
          label="Distance Driven"
          value={`${summary.total_distance_km.toFixed(1)} km`}
          sub={`${summary.total_passengers} passenger${summary.total_passengers === 1 ? "" : "s"} carried`}
        />
      </div>

      {/* Unsettled rides are lost income, so they get a status treatment with an
          icon + label, never colour alone. */}
      {summary.unsettled_rides > 0 && (
        <div
          className="glass-card"
          style={{ padding: "14px 18px", marginBottom: 20, borderLeft: "3px solid var(--warning)" }}
        >
          <div style={{ color: "var(--warning)", fontWeight: 700, fontSize: "0.88rem", marginBottom: 4 }}>
            ⚠️ {taka(summary.unsettled_value)} uncollected across {summary.unsettled_rides} ride
            {summary.unsettled_rides === 1 ? "" : "s"}
          </div>
          <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
            {summary.fully_unpaid_rides > 0 && (
              <>{summary.fully_unpaid_rides} ride{summary.fully_unpaid_rides === 1 ? "" : "s"} went
              entirely unpaid{summary.partially_paid_rides > 0 ? "; " : ". "}</>
            )}
            {summary.partially_paid_rides > 0 && (
              <>{summary.partially_paid_rides} ride{summary.partially_paid_rides === 1 ? "" : "s"}{" "}
              settled only partially, where some passengers paid and others could not. </>
            )}
            A fare goes uncollected when a passenger&apos;s wallet cannot cover their share, or the
            ride finished before wallets existed. Only money actually received is counted above.
          </div>
        </div>
      )}

      {/* Weekly earnings — change over time across few discrete buckets, so bars */}
      <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline",
                      marginBottom: 20, flexWrap: "wrap", gap: 10 }}>
          <div>
            <h2 style={{ fontSize: "1.05rem" }}>
              {period === "week" ? "Weekly" : "Daily"} Earnings
            </h2>
            <p style={{ fontSize: "0.76rem", color: "var(--text-tertiary)", marginTop: 2 }}>
              {period === "week"
                ? "Last 8 weeks · Asia/Dhaka · week starts Monday"
                : "Last 14 days · Asia/Dhaka"}
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ display: "flex", gap: 4 }}>
              {(["day", "week"] as Period[]).map(p2 => (
                <button
                  key={p2}
                  onClick={() => setPeriod(p2)}
                  className={`btn btn-sm ${period === p2 ? "btn-primary" : "btn-ghost"}`}
                >
                  {p2 === "day" ? "Daily" : "Weekly"}
                </button>
              ))}
            </div>
            <button onClick={() => setAsTable(v => !v)} className="btn btn-ghost btn-sm">
              {asTable ? "Show chart" : "Show table"}
            </button>
          </div>
        </div>

        {!hasEarnings ? (
          <p style={{ color: "var(--text-tertiary)", fontSize: "0.88rem", padding: "20px 0" }}>
            No earnings yet. Offer a ride from{" "}
            <Link href="/dashboard/rides" style={{ color: "var(--primary)" }}>Rides &amp; Surge</Link>{" "}
            — once it completes, the fare lands in your wallet and shows up here.
          </p>
        ) : asTable ? (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr><th>{period === "week" ? "Week beginning" : "Day"}</th><th style={{ textAlign: "right" }}>Rides</th><th style={{ textAlign: "right" }}>Earned</th></tr>
              </thead>
              <tbody>
                {buckets.map(w => (
                  <tr key={w.period_start}>
                    <td>{w.label}{w.is_current && (period === "week" ? " (current)" : " (today)")}</td>
                    <td style={{ textAlign: "right" }}>{w.rides}</td>
                    <td style={{ textAlign: "right", fontWeight: 600 }}>{taka(w.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ position: "relative" }}>
            {/* Recessive gridlines + y labels */}
            <div style={{ position: "relative", height: 200, marginLeft: 54 }}>
              {[1, 0.75, 0.5, 0.25, 0].map(f => (
                <div key={f} style={{ position: "absolute", left: 0, right: 0, bottom: `${f * 100}%`,
                                      borderTop: "1px solid var(--surface-border)" }}>
                  <span style={{ position: "absolute", right: "100%", paddingRight: 10, top: -7,
                                 fontSize: "0.68rem", color: "var(--text-tertiary)", whiteSpace: "nowrap" }}>
                    {axisMax > 0 ? Math.round(axisMax * f).toLocaleString() : 0}
                  </span>
                </div>
              ))}

              {/* Bars: anchored to the baseline, 4px rounded data-end, 2px gap */}
              <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "flex-end", gap: 2 }}>
                {buckets.map((w, i) => {
                  const pct = axisMax > 0 ? (w.amount / axisMax) * 100 : 0;
                  const isPeak = w.amount === maxBucket && maxBucket > 0;
                  const active = hover === i;
                  return (
                    <div
                      key={w.period_start}
                      onMouseEnter={() => setHover(i)}
                      onMouseLeave={() => setHover(null)}
                      style={{ flex: 1, height: "100%", display: "flex", alignItems: "flex-end",
                               position: "relative", cursor: "default" }}
                    >
                      {/* Direct labels only on the peak and the current week */}
                      {(isPeak || w.is_current) && w.amount > 0 && !active && (
                        <div style={{ position: "absolute", bottom: `calc(${pct}% + 6px)`, left: 0, right: 0,
                                      textAlign: "center", fontSize: "0.68rem", fontWeight: 700,
                                      color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                          {Math.round(w.amount).toLocaleString()}
                        </div>
                      )}
                      <div
                        style={{
                          width: "100%",
                          height: `${Math.max(pct, w.amount > 0 ? 1.5 : 0)}%`,
                          background: active ? SERIES_HOVER : SERIES,
                          borderRadius: "4px 4px 0 0",
                          transition: "background 150ms ease",
                          opacity: w.is_current ? 1 : 0.82,
                        }}
                      />
                      {active && w.amount >= 0 && (
                        <div
                          style={{
                            position: "absolute", bottom: `calc(${pct}% + 10px)`, left: "50%",
                            transform: "translateX(-50%)", background: "var(--bg-tertiary)",
                            border: "1px solid var(--surface-border)", borderRadius: "var(--radius-md)",
                            padding: "8px 12px", whiteSpace: "nowrap", zIndex: 5,
                            boxShadow: "var(--shadow-md)", pointerEvents: "none",
                          }}
                        >
                          <div style={{ fontSize: "0.7rem", color: "var(--text-tertiary)" }}>
                            {period === "week" ? `Week of ${w.label}` : w.label}
                          </div>
                          <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)" }}>
                            {taka(w.amount)}
                          </div>
                          <div style={{ fontSize: "0.7rem", color: "var(--text-tertiary)" }}>
                            {w.rides} ride{w.rides === 1 ? "" : "s"}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* X labels */}
            <div style={{ display: "flex", gap: 2, marginLeft: 54, marginTop: 8 }}>
              {buckets.map(w => (
                <div key={w.period_start} style={{ flex: 1, textAlign: "center", fontSize: "0.68rem",
                       color: w.is_current ? "var(--text-secondary)" : "var(--text-tertiary)",
                       fontWeight: w.is_current ? 700 : 400 }}>
                  {w.label}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Per-ride detail */}
      <div className="glass-card" style={{ padding: 24, marginBottom: 20 }}>
        <h2 style={{ fontSize: "1.05rem", marginBottom: 16 }}>Ride Breakdown</h2>
        {rides.length === 0 ? (
          <p style={{ color: "var(--text-tertiary)", fontSize: "0.88rem" }}>No completed rides yet.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Route</th><th style={{ textAlign: "right" }}>Pax</th>
                  <th style={{ textAlign: "right" }}>Fare</th>
                  {summary.total_platform_fees > 0 && <th style={{ textAlign: "right" }}>Fee</th>}
                  <th style={{ textAlign: "right" }}>You earned</th><th>When</th>
                </tr>
              </thead>
              <tbody>
                {rides.map(r => (
                  <tr key={r.ride_id}>
                    <td>
                      <span style={{ color: "var(--text-primary)" }}>{r.source} → {r.destination}</span>
                      {!r.settled ? (
                        <span className="badge badge-warning" style={{ marginLeft: 8 }}>⚠️ unpaid</span>
                      ) : r.shortfall > 0 ? (
                        <span className="badge badge-warning" style={{ marginLeft: 8 }}>
                          ⚠️ short {taka(r.shortfall)}
                        </span>
                      ) : null}
                      {r.distance_km ? (
                        <div style={{ fontSize: "0.72rem", color: "var(--text-tertiary)" }}>
                          {r.distance_km.toFixed(1)} km
                        </div>
                      ) : null}
                    </td>
                    <td style={{ textAlign: "right", color: "var(--text-secondary)" }}>{r.passengers}</td>
                    <td style={{ textAlign: "right", color: "var(--text-secondary)" }}>{taka(r.gross)}</td>
                    {summary.total_platform_fees > 0 && (
                      <td style={{ textAlign: "right", color: "var(--text-tertiary)" }}>
                        {r.platform_fee ? "−" + taka(r.platform_fee) : "—"}
                      </td>
                    )}
                    <td style={{ textAlign: "right", fontWeight: 700,
                                 color: r.settled ? "var(--success)" : "var(--text-tertiary)" }}>
                      {r.settled ? taka(r.net) : "—"}
                    </td>
                    <td style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", whiteSpace: "nowrap" }}>
                      {r.when ? new Date(r.when.replace(" ", "T") + "Z").toLocaleDateString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Link href="/dashboard/wallet" className="btn btn-primary">💳 Go to Wallet to cash out</Link>
        <Link href="/dashboard/rides" className="btn btn-ghost">🚗 Offer another ride</Link>
      </div>
    </div>
  );
}

"""
Arooohi Backend — Peak Hour Surge Indicator Routes
Feature 13: Peak Hour Surge Indicator  (Ornab)
Surge multiplier = seeded hourly demand baseline blended with live ride volume.
Blend makes it dynamic (FR-9) while keeping a meaningful value in a fresh demo.
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from app.database import get_db
from app.auth import get_current_user_id

router = APIRouter()

MIN_SURGE = 1.0
MAX_SURGE = 2.0
ACTIVE_RIDE_BUMP = 0.1   # per active ride (capped)
MAX_ACTIVE_FOR_BUMP = 5  # cap bump at 5 active rides


def _compute_multiplier(demand: float, active_rides: int) -> float:
    bump = min(active_rides, MAX_ACTIVE_FOR_BUMP) * ACTIVE_RIDE_BUMP
    return round(max(MIN_SURGE, min(MAX_SURGE, demand + bump)), 1)


def _label_for(multiplier: float) -> str:
    if multiplier >= 1.5:
        return "Peak"
    if multiplier >= 1.3:
        return "High"
    if multiplier > 1.0:
        return "Elevated"
    return "Normal"


def compute_current_multiplier(conn) -> tuple:
    """Shared helper: (multiplier, demand, active_rides) at the current hour.
    Used by /surge/current and by ride creation (cost splitter needs the surge)."""
    hour = datetime.utcnow().hour
    row = conn.execute("SELECT demand FROM surge_config WHERE hour = ?", (hour,)).fetchone()
    active = conn.execute("SELECT COUNT(*) AS c FROM rides WHERE status = 'active'").fetchone()["c"]
    demand = row["demand"] if row else 1.0
    multiplier = _compute_multiplier(demand, active)
    return multiplier, demand, active


@router.get("/current")
def get_current_surge(user_id: str = Depends(get_current_user_id)):
    """Current surge multiplier + label based on the hour and live ride volume."""
    conn = get_db()
    multiplier, demand, active = compute_current_multiplier(conn)
    conn.close()
    return {
        "hour": datetime.utcnow().hour,
        "demand": demand,
        "active_rides": active,
        "multiplier": multiplier,
        "label": _label_for(multiplier),
        "message": f"Surge ×{multiplier} — {_label_for(multiplier)} hours",
    }


@router.get("/schedule")
def get_surge_schedule(user_id: str = Depends(get_current_user_id)):
    """Hourly surge schedule (0-23) — used to warn users of upcoming peak windows."""
    conn = get_db()
    rows = conn.execute("SELECT hour, demand, label FROM surge_config ORDER BY hour ASC").fetchall()
    active = conn.execute("SELECT COUNT(*) AS c FROM rides WHERE status = 'active'").fetchone()["c"]
    conn.close()

    schedule = []
    for r in rows:
        m = _compute_multiplier(r["demand"], active)
        schedule.append({
            "hour": r["hour"],
            "demand": r["demand"],
            "multiplier": m,
            "label": _label_for(m),
        })

    return {"schedule": schedule}

"""Surge model: business rules and persistence, independent of FastAPI."""
from datetime import datetime
from zoneinfo import ZoneInfo
from app.models.database import get_db
from app.models.errors import DomainError

MIN_SURGE = 1.0
MAX_SURGE = 2.0
ACTIVE_RIDE_BUMP = 0.1   # per active ride (capped)
MAX_ACTIVE_FOR_BUMP = 5  # cap bump at 5 active rides
BD_TZ = ZoneInfo("Asia/Dhaka")


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
    hour = datetime.now(BD_TZ).hour
    row = conn.execute("SELECT demand FROM surge_config WHERE hour = ?", (hour,)).fetchone()
    active = conn.execute("SELECT COUNT(*) AS c FROM rides WHERE status = 'active'").fetchone()["c"]
    demand = row["demand"] if row else 1.0
    multiplier = _compute_multiplier(demand, active)
    return multiplier, demand, active


def get_current_surge(user_id: str):
    """Current surge multiplier + label based on the hour and live ride volume.

    Improvement note:
    - The surge state remains a lightweight live demand indicator for the ride planner view.
    """
    conn = get_db()
    multiplier, demand, active = compute_current_multiplier(conn)
    conn.close()
    return {
        "hour": datetime.now(BD_TZ).hour,
        "demand": demand,
        "active_rides": active,
        "multiplier": multiplier,
        "label": _label_for(multiplier),
        "message": f"Surge ×{multiplier} — {_label_for(multiplier)} hours",
    }


def get_surge_schedule(user_id: str):
    """Hourly surge schedule (0-23) — used to warn users of upcoming peak windows.

    Fix (PROJECT_PLAN.md §6.2): the live active-ride bump now applies ONLY to the
    current hour. Other hours show their seeded baseline so the schedule reads as a
    proper forecast instead of shifting all 24 hours by the same amount.
    """
    conn = get_db()
    rows = conn.execute("SELECT hour, demand, label FROM surge_config ORDER BY hour ASC").fetchall()
    active = conn.execute("SELECT COUNT(*) AS c FROM rides WHERE status = 'active'").fetchone()["c"]
    current_hour = datetime.now(BD_TZ).hour
    conn.close()

    schedule = []
    for r in rows:
        hour = r["hour"]
        is_current = hour == current_hour
        # Live bump only on the current hour; elsewhere baseline only.
        m = _compute_multiplier(r["demand"], active if is_current else 0)
        schedule.append({
            "hour": hour,
            "demand": r["demand"],
            "multiplier": m,
            "label": _label_for(m),
            "is_current": is_current,
        })

    return {"schedule": schedule}

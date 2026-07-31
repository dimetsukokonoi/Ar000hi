"""
Arooohi Backend — Eco/Footprint Tracker Routes
Feature 20: Eco/Footprint Tracker  (Ornab)
CO2 saved by carpooling vs driving solo (SRS FR-12).
Per completed ride:
  solo_kg   = distance_km x 0.13 kg/km  (avg petrol car ~130 g/km)
  shared_kg = solo_kg / occupancy       (occupancy = driver + accepted passengers)
  saved_kg  = solo_kg - shared_kg       (0 when riding solo)

Improvements in this pass:
- COALESCE(distance_km, 0) guard so a NULL distance can never crash the math.
- Added GET /api/eco/leaderboard — top CO2 savers (gamified public ranking).
"""
from fastapi import APIRouter, Depends
from app.database import get_db
from app.auth import get_current_user_id

router = APIRouter()

G_CO2_PER_KM = 0.13          # kg CO2 per km for a solo petrol car
KG_PER_TREE = 21.0           # ~1 tree absorbs 21 kg CO2 per year
FUEL_L_PER_KM = 0.07         # ~7 L / 100 km, for a fuel-saved estimate


def _occupancy(accepted_count: int) -> int:
    """Driver + accepted passengers."""
    return max(accepted_count + 1, 1)


@router.get("/stats")
def get_eco_stats(user_id: str = Depends(get_current_user_id)):
    """Aggregate eco stats for the current user across their completed rides."""
    conn = get_db()

    rides = conn.execute(
        """SELECT r.id, COALESCE(r.distance_km, 0) AS distance_km,
                  (SELECT COUNT(*) FROM ride_passengers rp
                   WHERE rp.ride_id = r.id AND rp.status IN ('accepted','completed')) AS passenger_count
           FROM rides r
           WHERE r.status = 'completed'
             AND r.distance_km IS NOT NULL
             AND r.distance_km > 0
             AND (r.driver_id = ?
                  OR r.id IN (SELECT ride_id FROM ride_passengers WHERE passenger_id = ?))
           ORDER BY r.ended_at DESC""",
        (user_id, user_id)
    ).fetchall()
    conn.close()

    trips = 0
    total_km = 0.0
    total_saved_kg = 0.0
    total_solo_kg = 0.0
    total_fuel_l = 0.0

    ride_breakdown = []
    for r in rides:
        occ = _occupancy(r["passenger_count"])
        solo_kg = r["distance_km"] * G_CO2_PER_KM
        shared_kg = solo_kg / occ if occ > 1 else solo_kg
        saved_kg = max(solo_kg - shared_kg, 0.0)

        trips += 1
        total_km += r["distance_km"]
        total_saved_kg += saved_kg
        total_solo_kg += solo_kg
        total_fuel_l += r["distance_km"] * FUEL_L_PER_KM

        ride_breakdown.append({
            "ride_id": r["id"],
            "distance_km": r["distance_km"],
            "occupancy": occ,
            "solo_kg": round(solo_kg, 2),
            "shared_kg": round(shared_kg, 2),
            "saved_kg": round(saved_kg, 2),
        })

    trees_equivalent = total_saved_kg / KG_PER_TREE

    return {
        "trips": trips,
        "total_km": round(total_km, 2),
        "total_solo_kg": round(total_solo_kg, 2),
        "total_saved_kg": round(total_saved_kg, 2),
        "trees_equivalent": round(trees_equivalent, 2),
        "fuel_saved_l": round(total_fuel_l, 2),
        "rides": ride_breakdown,
    }


@router.get("/leaderboard")
def get_eco_leaderboard(user_id: str = Depends(get_current_user_id)):
    """Gamified public ranking of top CO2 savers (Feature 20 improvement).

    Aggregates saved_kg per user across completed rides they drove OR joined,
    then returns the top 10. The requesting user's own rank is also included
    if they fall outside the top 10.
    """
    conn = get_db()
    rows = conn.execute(
        """WITH completed AS (
               SELECT r.id AS ride_id, r.driver_id, COALESCE(r.distance_km, 0) AS distance_km
               FROM rides r
               WHERE r.status = 'completed' AND r.distance_km IS NOT NULL AND r.distance_km > 0
           ),
           driver_km AS (
               SELECT driver_id AS user_id, SUM(distance_km) AS dist_km, COUNT(*) AS trips
               FROM completed GROUP BY driver_id
           ),
           passenger_km AS (
               SELECT rp.passenger_id AS user_id, SUM(c.distance_km) AS dist_km,
                      COUNT(DISTINCT c.ride_id) AS trips
               FROM ride_passengers rp JOIN completed c ON rp.ride_id = c.ride_id
               WHERE rp.status IN ('accepted', 'completed')
               GROUP BY rp.passenger_id
           ),
           all_users AS (
               SELECT user_id, SUM(dist_km) AS dist_km, SUM(trips) AS trips FROM (
                   SELECT user_id, dist_km, trips FROM driver_km
                   UNION ALL
                   SELECT user_id, dist_km, trips FROM passenger_km
               ) GROUP BY user_id
           )
           SELECT u.name, u.id AS user_id, au.dist_km, au.trips
           FROM all_users au JOIN users u ON u.id = au.user_id
           ORDER BY au.dist_km DESC LIMIT 10"""
    ).fetchall()
    conn.close()

    leaderboard = []
    for i, r in enumerate(rows, start=1):
        # approximate saved_kg from distance + avg occupancy for display purposes
        saved_kg = round((r["dist_km"] or 0) * G_CO2_PER_KM * 0.5, 2)
        leaderboard.append({
            "rank": i,
            "user_id": r["user_id"],
            "name": r["name"],
            "distance_km": round(r["dist_km"] or 0, 2),
            "trips": r["trips"],
            "saved_kg_approx": saved_kg,
        })

    return {"leaderboard": leaderboard}

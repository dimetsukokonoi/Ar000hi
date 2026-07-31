"""
Arooohi Backend — Eco/Footprint Tracker Routes
Feature 20: Eco/Footprint Tracker  (Ornab)
CO2 saved by carpooling vs driving solo (SRS FR-12).
Per completed ride:
  solo_kg   = distance_km x 0.13 kg/km  (avg petrol car ~130 g/km)
  shared_kg = solo_kg / occupancy       (occupancy = driver + accepted passengers)
  saved_kg  = solo_kg - shared_kg       (0 when riding solo)
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
        """SELECT r.id, r.distance_km,
                  (SELECT COUNT(*) FROM ride_passengers rp
                   WHERE rp.ride_id = r.id AND rp.status IN ('accepted','completed')) AS passenger_count
           FROM rides r
           WHERE r.status = 'completed'
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

"""
Comprehensive Test Suite for Arooohi Campus Features:
1. Campus Pickup Hotspots
2. Female-Only Ride Mode
3. Multi-Stop Ride Support
4. Scheduled Ride Booking
5. Campus Zone Smart Matching
"""
import os
import sys
import uuid
import pytest
from datetime import datetime as dt, timedelta
from fastapi.testclient import TestClient

# Ensure backend root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Use a test database
os.environ["DATABASE_PATH"] = "/tmp/test_arooohi.db"
if os.path.exists("/tmp/test_arooohi.db"):
    os.remove("/tmp/test_arooohi.db")

from app.database import init_db, get_db
from app.main import app
from app.auth import create_access_token, hash_password

init_db()
client = TestClient(app)


def _create_user(name: str, email: str, role: str = "rider", gender: str = "other", is_verified: bool = True):
    uid = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        """INSERT INTO users (id, name, bracu_email, password_hash, role, gender, is_verified)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (uid, name, email, hash_password("Password123!"), role, gender, 1 if is_verified else 0)
    )
    conn.commit()
    conn.close()
    token = create_access_token({"sub": uid})
    return uid, token, {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module", autouse=True)
def setup_test_users():
    global female_driver_h, male_driver_h, female_rider_h, male_rider_h
    _, _, female_driver_h = _create_user("Fatima Driver", "fatima.driver@g.bracu.ac.bd", gender="female")
    _, _, male_driver_h = _create_user("Rahim Driver", "rahim.driver@g.bracu.ac.bd", gender="male")
    _, _, female_rider_h = _create_user("Ayesha Rider", "ayesha.rider@g.bracu.ac.bd", gender="female")
    _, _, male_rider_h = _create_user("Karim Rider", "karim.rider@g.bracu.ac.bd", gender="male")


def test_campus_hotspots():
    """Test 1: Hotspots API returns categorized locations."""
    res = client.get("/api/rides/hotspots")
    assert res.status_code == 200
    hotspots = res.json()
    assert len(hotspots) >= 8
    categories = {h["category"] for h in hotspots}
    assert "campus_gate" in categories
    assert "academic" in categories
    assert "transit_hub" in categories
    gate1 = next(h for h in hotspots if h["id"] == "gate 1")
    assert gate1["name"] == "Gate 1 (Main Entrance - Pragati Sarani)"
    assert gate1["lat"] == 23.7745
    assert gate1["lng"] == 90.4255


def test_female_only_mode_creation_and_joining():
    """Test 2: Female-only mode gating."""
    future_time = (dt.utcnow() + timedelta(hours=2)).isoformat()

    # Male driver attempting to create female-only ride -> 403 Forbidden
    res = client.post(
        "/api/rides",
        json={
            "source": "Mohakhali",
            "destination": "Gate 1",
            "base_fare": 120.0,
            "total_seats": 3,
            "scheduled_at": future_time,
            "female_only": True
        },
        headers=male_driver_h
    )
    assert res.status_code == 403
    assert "Only female drivers" in res.json()["detail"]

    # Female driver creating female-only ride -> 200 Success
    res = client.post(
        "/api/rides",
        json={
            "source": "Mohakhali",
            "destination": "Gate 1",
            "base_fare": 120.0,
            "total_seats": 3,
            "scheduled_at": future_time,
            "female_only": True
        },
        headers=female_driver_h
    )
    assert res.status_code == 200
    ride_id = res.json()["ride_id"]

    # Male rider attempting to join female-only ride -> 403 Forbidden
    res = client.post(
        f"/api/rides/{ride_id}/join",
        json={"seats": 1},
        headers=male_rider_h
    )
    assert res.status_code == 403
    assert "female-only ride" in res.json()["detail"]

    # Female rider joining female-only ride -> 200 Success
    res = client.post(
        f"/api/rides/{ride_id}/join",
        json={"seats": 1},
        headers=female_rider_h
    )
    assert res.status_code == 200
    assert res.json()["status"] == "requested"


def test_multi_stop_ride_and_status_tracking():
    """Test 3: Multi-stop ride creation, stop joining, status tracking, and split calculation."""
    future_time = (dt.utcnow() + timedelta(hours=3)).isoformat()

    # Driver creates ride with intermediate stops
    res = client.post(
        "/api/rides",
        json={
            "source": "Mirpur",
            "destination": "Gate 1",
            "base_fare": 150.0,
            "total_seats": 4,
            "scheduled_at": future_time,
            "female_only": False,
            "stops": ["Banani", "Mohakhali"]
        },
        headers=male_driver_h
    )
    assert res.status_code == 200
    ride_id = res.json()["ride_id"]

    # Passenger joins specifying pickup at Banani and dropoff at Mohakhali
    res = client.post(
        f"/api/rides/{ride_id}/join",
        json={"seats": 1, "pickup_stop": "Banani", "dropoff_stop": "Mohakhali"},
        headers=male_rider_h
    )
    assert res.status_code == 200
    pid = res.json()["passenger_id"]
    assert res.json()["pickup_stop"] == "Banani"
    assert res.json()["dropoff_stop"] == "Mohakhali"

    # Driver accepts passenger
    res = client.post(f"/api/rides/{ride_id}/accept/{pid}", headers=male_driver_h)
    assert res.status_code == 200

    # Inspect ride details
    res = client.get(f"/api/rides/{ride_id}", headers=male_driver_h)
    assert res.status_code == 200
    ride_data = res.json()
    assert len(ride_data["stops"]) == 2
    stop1 = ride_data["stops"][0]
    assert stop1["place"] == "Banani"
    assert stop1["status"] == "pending"

    # Driver marks stop 1 as reached
    res = client.post(
        f"/api/rides/{ride_id}/stops/{stop1['id']}/status",
        json={"status": "reached"},
        headers=male_driver_h
    )
    assert res.status_code == 200
    assert res.json()["status"] == "reached"

    # Fare split verification
    res = client.get(f"/api/rides/{ride_id}/split", headers=male_driver_h)
    assert res.status_code == 200
    split_data = res.json()
    assert len(split_data["breakdown"]) == 1
    assert split_data["breakdown"][0]["pickup_stop"] == "Banani"
    assert split_data["breakdown"][0]["dropoff_stop"] == "Mohakhali"


def test_smart_matching_algorithm():
    """Test 4: Smart Matching algorithm with multi-stop and class schedule scoring."""
    future_8am = (dt.utcnow().replace(hour=8, minute=0, second=0) + timedelta(days=1)).isoformat()

    # Create Ride 1: Banani to Gate 1 scheduled at 8:00 AM
    res1 = client.post(
        "/api/rides",
        json={
            "source": "Banani",
            "destination": "Gate 1",
            "base_fare": 80.0,
            "total_seats": 4,
            "scheduled_at": future_8am,
            "female_only": False,
            "stops": ["UB Building"]
        },
        headers=male_driver_h
    )
    assert res1.status_code == 200
    ride1_id = res1.json()["ride_id"]

    # Match request for student going from Banani to UB Building around 08:00 AM
    match_res = client.get(
        "/api/rides/match?source=Banani&destination=UB%20Building&scheduled_time=08:00",
        headers=female_rider_h
    )
    assert match_res.status_code == 200
    matches = match_res.json()
    assert len(matches) > 0

    best_match = next((m for m in matches if m["id"] == ride1_id), None)
    assert best_match is not None
    assert best_match["match_score"] >= 80
    reasons_str = " ".join(best_match["match_reasons"])
    assert "Exact Pickup Point" in reasons_str
    assert "Multi-Stop Route Match" in reasons_str or "Direct Destination Match" in reasons_str
    assert "Class Time Match" in reasons_str


def test_scheduled_ride_validation():
    """Test 5: Scheduled ride booking with past date rejection."""
    past_time = (dt.utcnow() - timedelta(hours=1)).isoformat()
    res = client.post(
        "/api/rides",
        json={
            "source": "Gulshan",
            "destination": "Gate 1",
            "base_fare": 100.0,
            "scheduled_at": past_time,
            "female_only": False
        },
        headers=male_driver_h
    )
    assert res.status_code == 400
    assert "Scheduled time must be in the future" in res.json()["detail"]


def test_badda_campus_zone_proximity_matching():
    """Test 6: Campus Zone Proximity matching on Merul Badda campus."""
    future_time = (dt.utcnow() + timedelta(hours=4)).isoformat()
    # Driver creates ride ending at Gate 1 (Pragati Sarani)
    res = client.post(
        "/api/rides",
        json={
            "source": "Aftabnagar",
            "destination": "Gate 1",
            "base_fare": 60.0,
            "total_seats": 3,
            "scheduled_at": future_time,
            "female_only": False,
            "stops": []
        },
        headers=male_driver_h
    )
    assert res.status_code == 200
    ride_id = res.json()["ride_id"]

    # Student searches for ride from Hatirjheel Ghat to Library (both adjacent Badda campus points)
    match_res = client.get(
        "/api/rides/match?pickup=Hatirjheel%20Ghat&dropoff=Library",
        headers=female_rider_h
    )
    assert match_res.status_code == 200
    matches = match_res.json()
    badda_match = next((m for m in matches if m["id"] == ride_id), None)
    assert badda_match is not None
    assert badda_match["match_score"] >= 70
    reasons_str = " ".join(badda_match["match_reasons"])
    assert "BRACU Campus Zone Drop-off" in reasons_str or "Near Drop-off" in reasons_str


if __name__ == "__main__":
    pytest.main(["-v", __file__])


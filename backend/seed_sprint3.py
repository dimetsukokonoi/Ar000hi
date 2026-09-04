"""
Seed script to create clean demo users and rides for Sprint-3 screenshots.
"""
import uuid
from datetime import datetime as dt, timedelta
import sqlite3
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.database import get_db, init_db
from app.auth import hash_password

init_db()
conn = get_db()

# Create or update demo users
users = [
    ("usr_ayesha", "Ayesha Rahman", "ayesha.rider@g.bracu.ac.bd", "01711223344", "female", "rider"),
    ("usr_fatima", "Fatima Farooq", "fatima.driver@g.bracu.ac.bd", "01811223344", "female", "driver"),
    ("usr_rahim", "Rahim Ahmed", "rahim.driver@g.bracu.ac.bd", "01911223344", "male", "driver"),
    ("usr_tanvir", "Tanvir Hasan", "tanvir.driver@g.bracu.ac.bd", "01611223344", "male", "driver"),
]

for uid, name, email, phone, gender, role in users:
    exists = conn.execute("SELECT id FROM users WHERE bracu_email = ?", (email,)).fetchone()
    if exists:
        conn.execute(
            "UPDATE users SET name = ?, phone = ?, gender = ?, role = ?, is_verified = 1 WHERE bracu_email = ?",
            (name, phone, gender, role, email)
        )
    else:
        conn.execute(
            """INSERT INTO users (id, name, bracu_email, phone, password_hash, gender, role, is_verified, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1)""",
            (uid, name, email, phone, hash_password("Password123!"), gender, role)
        )

# Get Fatima and Rahim user IDs
f_driver = conn.execute("SELECT id FROM users WHERE bracu_email = 'fatima.driver@g.bracu.ac.bd'").fetchone()["id"]
r_driver = conn.execute("SELECT id FROM users WHERE bracu_email = 'rahim.driver@g.bracu.ac.bd'").fetchone()["id"]
t_driver = conn.execute("SELECT id FROM users WHERE bracu_email = 'tanvir.driver@g.bracu.ac.bd'").fetchone()["id"]
ayesha_rider = conn.execute("SELECT id FROM users WHERE bracu_email = 'ayesha.rider@g.bracu.ac.bd'").fetchone()["id"]

# Clean old demo rides
conn.execute("DELETE FROM ride_stops WHERE ride_id IN (SELECT id FROM rides WHERE driver_id IN (?, ?, ?))", (f_driver, r_driver, t_driver))
conn.execute("DELETE FROM ride_passengers WHERE ride_id IN (SELECT id FROM rides WHERE driver_id IN (?, ?, ?))", (f_driver, r_driver, t_driver))
conn.execute("DELETE FROM rides WHERE driver_id IN (?, ?, ?)", (f_driver, r_driver, t_driver))

tomorrow = dt.utcnow() + timedelta(days=1)
time_8am = tomorrow.replace(hour=8, minute=0, second=0, microsecond=0).isoformat()
time_930am = tomorrow.replace(hour=9, minute=30, second=0, microsecond=0).isoformat()
time_11am = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0).isoformat()

# Ride 1: Female-only ride from Dhanmondi to Gate 1 (Pragati Sarani) with Multi-stops
ride1_id = "ride_female_01"
conn.execute(
    """INSERT INTO rides (id, driver_id, source, destination, base_fare, total_seats, scheduled_at, female_only, status)
       VALUES (?, ?, 'Dhanmondi', 'Gate 1 (Main Entrance - Pragati Sarani)', 120.0, 3, ?, 1, 'scheduled')""",
    (ride1_id, f_driver, time_8am)
)
# Stops for Ride 1
conn.execute("INSERT INTO ride_stops (id, ride_id, sequence, place, status) VALUES (?, ?, 1, 'Hatirjheel Merul Badda Water Taxi Ghat', 'pending')", (str(uuid.uuid4()), ride1_id))
conn.execute("INSERT INTO ride_stops (id, ride_id, sequence, place, status) VALUES (?, ?, 2, 'BRACU Main Academic Complex', 'pending')", (str(uuid.uuid4()), ride1_id))

# Ride 2: Multi-stop morning carpool from Banasree to Gate 1 via Aftabnagar and Rampura Bridge
ride2_id = "ride_multi_02"
conn.execute(
    """INSERT INTO rides (id, driver_id, source, destination, base_fare, total_seats, scheduled_at, female_only, status)
       VALUES (?, ?, 'Banasree', 'Gate 1 (Main Entrance - Pragati Sarani)', 75.0, 4, ?, 0, 'scheduled')""",
    (ride2_id, r_driver, time_8am)
)
stop1_id = str(uuid.uuid4())
stop2_id = str(uuid.uuid4())
conn.execute("INSERT INTO ride_stops (id, ride_id, sequence, place, status) VALUES (?, ?, 1, 'Rampura Bridge / DIT Road', 'reached')", (stop1_id, ride2_id))
conn.execute("INSERT INTO ride_stops (id, ride_id, sequence, place, status) VALUES (?, ?, 2, 'Aftabnagar Main Gate (Block A)', 'pending')", (stop2_id, ride2_id))
conn.execute("INSERT INTO ride_stops (id, ride_id, sequence, place, status) VALUES (?, ?, 3, 'Ayesha Abed Library (Level 3-4)', 'pending')", (str(uuid.uuid4()), ride2_id))

# Passenger joining Ride 2 (leave unjoined for testing multi-stop interactive modal)
# conn.execute(
#     """INSERT INTO ride_passengers (id, ride_id, passenger_id, seats, pickup_stop, dropoff_stop, status)
#        VALUES (?, ?, ?, 1, 'Rampura Bridge / DIT Road', 'Ayesha Abed Library (Level 3-4)', 'accepted')""",
#     (str(uuid.uuid4()), ride2_id, ayesha_rider)
# )

# Ride 3: Northern Corridor Scheduled ride (Kuril / Bashundhara -> Gate 2 Hatirjheel)
ride3_id = "ride_kuril_03"
conn.execute(
    """INSERT INTO rides (id, driver_id, source, destination, base_fare, total_seats, scheduled_at, female_only, status)
       VALUES (?, ?, 'Bashundhara', 'Gate 2 (Hatirjheel / West Walkway)', 90.0, 4, ?, 0, 'scheduled')""",
    (ride3_id, t_driver, time_930am)
)
conn.execute("INSERT INTO ride_stops (id, ride_id, sequence, place, status) VALUES (?, ?, 1, 'Notun Bazar / Madani Ave (100 Feet)', 'pending')", (str(uuid.uuid4()), ride3_id))
conn.execute("INSERT INTO ride_stops (id, ride_id, sequence, place, status) VALUES (?, ?, 2, 'Main Cafeteria & Food Court', 'pending')", (str(uuid.uuid4()), ride3_id))

conn.commit()
conn.close()
print("Seeded demo users and Badda campus rides successfully!")

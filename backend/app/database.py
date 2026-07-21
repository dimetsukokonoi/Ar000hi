"""
Arooohi Backend — Database Layer (Python built-in sqlite3)
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "arooohi.db")


def get_db() -> sqlite3.Connection:
    """Get a database connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            bracu_email TEXT UNIQUE NOT NULL,
            phone TEXT DEFAULT '',
            password_hash TEXT NOT NULL,
            gender TEXT NOT NULL CHECK(gender IN ('male', 'female', 'other')),
            role TEXT NOT NULL DEFAULT 'rider' CHECK(role IN ('rider', 'driver', 'admin')),
            is_verified INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS otp_codes (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            is_used INTEGER NOT NULL DEFAULT 0,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS driver_profiles (
            id TEXT PRIMARY KEY,
            user_id TEXT UNIQUE NOT NULL REFERENCES users(id),
            nid_document_url TEXT,
            license_document_url TEXT,
            vehicle_registration_url TEXT,
            vehicle_type TEXT DEFAULT '',
            vehicle_model TEXT DEFAULT '',
            vehicle_plate TEXT DEFAULT '',
            verification_status TEXT NOT NULL DEFAULT 'pending'
                CHECK(verification_status IN ('pending', 'approved', 'rejected')),
            admin_notes TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS trusted_contacts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            contact_name TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            contact_email TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tracking_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            share_token TEXT UNIQUE NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tracking_points (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES tracking_sessions(id),
            user_id TEXT NOT NULL REFERENCES users(id),
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sos_alerts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            session_id TEXT REFERENCES tracking_sessions(id),
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active', 'resolved', 'false_alarm')),
            contacts_notified TEXT DEFAULT '[]',
            resolved_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS complaints (
            id TEXT PRIMARY KEY,
            reporter_id TEXT NOT NULL REFERENCES users(id),
            reported_id TEXT REFERENCES users(id),
            category TEXT NOT NULL
                CHECK(category IN ('safety', 'misconduct', 'vehicle', 'payment', 'other')),
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK(status IN ('open', 'under_review', 'resolved', 'dismissed')),
            admin_notes TEXT DEFAULT '',
            resolved_by TEXT REFERENCES users(id),
            resolved_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # Create default admin account
    import bcrypt
    admin_hash = bcrypt.hashpw("admin123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    try:
        conn.execute(
            """INSERT INTO users (id, name, bracu_email, phone, password_hash, gender, role, is_verified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("admin-001", "Campus Moderator", "admin@g.bracu.ac.bd", "01700000000",
             admin_hash, "other", "admin", 1)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Admin already exists

    conn.close()
    print(f"[OK] Database initialized at {DB_PATH}")

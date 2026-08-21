"""
Arooohi Backend — Database Layer (Python built-in sqlite3)
"""
import sqlite3
import os

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "arooohi.db"))


def get_db() -> sqlite3.Connection:
    """Get a database connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """Idempotently add a column to an existing table (lightweight migration).

    Used so `init_db()` can extend tables that already exist in older DB files
    without a full migration framework. (Ornab / cross-agent improvement pass)
    """
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


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

        -- Ornab: rides core + Ornab's feature tables (cost splitter, surge, chat, eco)
        CREATE TABLE IF NOT EXISTS rides (
            id TEXT PRIMARY KEY,
            driver_id TEXT NOT NULL REFERENCES users(id),
            source TEXT NOT NULL,
            destination TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled'
                CHECK(status IN ('scheduled', 'active', 'completed', 'cancelled')),
            distance_km REAL,
            base_fare REAL NOT NULL,
            surge_multiplier REAL NOT NULL DEFAULT 1.0,
            total_seats INTEGER NOT NULL DEFAULT 4,
            scheduled_at TEXT,
            started_at TEXT,
            ended_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ride_passengers (
            id TEXT PRIMARY KEY,
            ride_id TEXT NOT NULL REFERENCES rides(id),
            passenger_id TEXT NOT NULL REFERENCES users(id),
            seats INTEGER NOT NULL DEFAULT 1,
            pickup_stop TEXT DEFAULT '',
            dropoff_stop TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'requested'
                CHECK(status IN ('requested', 'accepted', 'completed', 'cancelled')),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ride_stops (
            id TEXT PRIMARY KEY,
            ride_id TEXT NOT NULL REFERENCES rides(id),
            sequence INTEGER NOT NULL,
            place TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending', 'reached', 'departed'))
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            ride_id TEXT NOT NULL REFERENCES rides(id),
            sender_id TEXT NOT NULL REFERENCES users(id),
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS surge_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hour INTEGER NOT NULL UNIQUE,
            demand REAL NOT NULL,
            label TEXT NOT NULL
        );

        -- Feature 9: Wallet & bKash (mock). One wallet row per user; every balance
        -- change is an append-only transaction so the ledger is auditable and the
        -- balance can always be re-derived from history.
        CREATE TABLE IF NOT EXISTS wallets (
            user_id TEXT PRIMARY KEY REFERENCES users(id),
            balance REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL
                CHECK(kind IN ('topup', 'fare', 'payout', 'penalty', 'refund')),
            amount REAL NOT NULL,          -- signed: positive = credit, negative = debit
            balance_after REAL NOT NULL,
            ride_id TEXT,
            method TEXT NOT NULL DEFAULT 'mock',
            reference TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Feature 7: Driver Rating & Review. UNIQUE(ride, reviewer, reviewee)
        -- enforces one review per person per ride at the DB level.
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            ride_id TEXT NOT NULL REFERENCES rides(id),
            reviewer_id TEXT NOT NULL REFERENCES users(id),
            reviewee_id TEXT NOT NULL REFERENCES users(id),
            stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
            comment TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(ride_id, reviewer_id, reviewee_id)
        );

        -- Ornab (Feature 12): persisted record of every auto-share so the
        -- "share to trusted contacts" action is auditable, not just console-logged.
        CREATE TABLE IF NOT EXISTS contact_shares (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            share_url TEXT NOT NULL,
            session_id TEXT,
            contact_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # ---- Lightweight migrations for existing DB files (idempotent) ----
    # rides.total_seats powers seat-aware cost splitting + join capacity checks.
    _ensure_column(conn, "rides", "total_seats", "INTEGER NOT NULL DEFAULT 4")
    # Female-only ride mode toggle
    _ensure_column(conn, "rides", "female_only", "INTEGER NOT NULL DEFAULT 0")
    # Multi-stop ride support: passenger specific pickup and dropoff stops
    _ensure_column(conn, "ride_passengers", "pickup_stop", "TEXT DEFAULT ''")
    _ensure_column(conn, "ride_passengers", "dropoff_stop", "TEXT DEFAULT ''")
    # Multi-stop live progress tracking
    _ensure_column(conn, "ride_stops", "status", "TEXT NOT NULL DEFAULT 'pending'")

    # Feature 18: Ride Cancellation Policy & Penalty.
    _ensure_column(conn, "rides", "cancelled_at", "TEXT")
    _ensure_column(conn, "rides", "cancelled_by", "TEXT")
    _ensure_column(conn, "rides", "cancel_reason", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "ride_passengers", "cancelled_at", "TEXT")
    _ensure_column(conn, "ride_passengers", "penalty_amount", "REAL NOT NULL DEFAULT 0")

    # SQLite hardening: WAL journal + indexes on the hot foreign keys.
    # (matches PROJECT_PLAN.md §6.3)
    conn.execute("PRAGMA journal_mode = WAL")
    for idx_sql in (
        "CREATE INDEX IF NOT EXISTS idx_ride_passengers_ride ON ride_passengers(ride_id)",
        "CREATE INDEX IF NOT EXISTS idx_ride_passengers_user ON ride_passengers(passenger_id)",
        "CREATE INDEX IF NOT EXISTS idx_ride_stops_ride ON ride_stops(ride_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_ride ON chat_messages(ride_id)",
        "CREATE INDEX IF NOT EXISTS idx_tracking_points_session ON tracking_points(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_trusted_contacts_user ON trusted_contacts(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_sos_alerts_user ON sos_alerts(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_contact_shares_user ON contact_shares(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_wallet_tx_user ON wallet_transactions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_wallet_tx_ride ON wallet_transactions(ride_id)",
        "CREATE INDEX IF NOT EXISTS idx_reviews_reviewee ON reviews(reviewee_id)",
        "CREATE INDEX IF NOT EXISTS idx_reviews_ride ON reviews(ride_id)",
        "CREATE INDEX IF NOT EXISTS idx_rides_driver_status ON rides(driver_id, status)",
    ):
        conn.execute(idx_sql)
    conn.commit()

    # Ornab: seed 24-hour peak-hour surge baseline (hour, demand, label)
    surge_seed = [
        (0, 1.1, "Normal"), (1, 1.0, "Normal"), (2, 1.0, "Normal"), (3, 1.0, "Normal"),
        (4, 1.0, "Normal"), (5, 1.1, "Normal"), (6, 1.2, "Elevated"), (7, 1.6, "Peak"),
        (8, 1.8, "Peak"), (9, 1.5, "Peak"), (10, 1.2, "Elevated"), (11, 1.3, "High"),
        (12, 1.4, "High"), (13, 1.3, "High"), (14, 1.1, "Normal"), (15, 1.1, "Normal"),
        (16, 1.4, "High"), (17, 1.7, "Peak"), (18, 1.8, "Peak"), (19, 1.6, "Peak"),
        (20, 1.4, "High"), (21, 1.3, "High"), (22, 1.2, "Elevated"), (23, 1.1, "Normal"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO surge_config (hour, demand, label) VALUES (?, ?, ?)",
        surge_seed
    )
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

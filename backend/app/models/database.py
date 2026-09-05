"""
Arooohi Backend — Database Layer (Python built-in sqlite3)
"""
import sqlite3
import os

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "arooohi.db"))


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


def _allow_penalty_kind(conn: sqlite3.Connection) -> None:
    """Add 'penalty' to transactions.kind on databases created before Feature 18.

    SQLite cannot ALTER a CHECK constraint, so the table has to be rebuilt. This
    is money data, so it is done inside one transaction and only when the current
    constraint is actually missing the value.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'"
    ).fetchone()
    if not row or "'penalty'" in row[0]:
        return   # fresh database, or already migrated

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript("""
        BEGIN;
        CREATE TABLE transactions_new (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL
                CHECK(kind IN ('topup', 'ride_debit', 'ride_credit',
                               'withdrawal', 'refund', 'commission', 'penalty')),
            amount REAL NOT NULL,
            platform_fee REAL NOT NULL DEFAULT 0.0,
            balance_after REAL NOT NULL,
            ride_id TEXT REFERENCES rides(id),
            payment_id TEXT,
            counterparty_id TEXT REFERENCES users(id),
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO transactions_new
            (id, user_id, kind, amount, platform_fee, balance_after, ride_id,
             payment_id, counterparty_id, note, created_at)
        SELECT id, user_id, kind, amount, platform_fee, balance_after, ride_id,
               payment_id, counterparty_id, note, created_at FROM transactions;
        DROP TABLE transactions;
        ALTER TABLE transactions_new RENAME TO transactions;
        COMMIT;
    """)
    conn.execute("PRAGMA foreign_keys = ON")
    print("[OK] migrated transactions.kind to allow 'penalty'")


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

        -- Feature 7: Driver Rating & Review
        -- UNIQUE(ride_id, reviewer_id, reviewee_id) is the whole anti-abuse story:
        -- one review per person, per ride, per target. No edits, no re-rating.
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

        -- Feature 9: Wallet & bKash Integration -------------------------------
        -- Prepaid wallet model: the gateway is touched only at the edges
        -- (top-up in, cash-out out). Ride settlement is an internal transfer.

        -- One wallet per user. `balance` is a cached total; the append-only
        -- `transactions` ledger is the source of truth. GET /api/wallet/reconcile
        -- asserts the two agree.
        CREATE TABLE IF NOT EXISTS wallets (
            id TEXT PRIMARY KEY,
            user_id TEXT UNIQUE NOT NULL REFERENCES users(id),
            balance REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Append-only ledger. NEVER updated or deleted: a correction is a new
        -- opposing row. `amount` is signed from the wallet owner's point of view
        -- (credit > 0, debit < 0), so balance == SUM(amount).
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL
                CHECK(kind IN ('topup', 'ride_debit', 'ride_credit',
                               'withdrawal', 'refund', 'commission', 'penalty')),
            amount REAL NOT NULL,
            platform_fee REAL NOT NULL DEFAULT 0.0,
            balance_after REAL NOT NULL,
            ride_id TEXT REFERENCES rides(id),
            payment_id TEXT,
            counterparty_id TEXT REFERENCES users(id),
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- One row per bKash checkout attempt. Mirrors the real tokenized-checkout
        -- lifecycle so swapping in the live gateway needs no schema change.
        CREATE TABLE IF NOT EXISTS bkash_payments (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            amount REAL NOT NULL,
            intent TEXT NOT NULL DEFAULT 'topup'
                CHECK(intent IN ('topup', 'withdrawal')),
            status TEXT NOT NULL DEFAULT 'created'
                CHECK(status IN ('created', 'authorized', 'completed',
                                 'failed', 'cancelled', 'timeout')),
            trx_id TEXT,
            wallet_number TEXT DEFAULT '',
            failure_reason TEXT DEFAULT '',
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
    # Feature 18: cancellation bookkeeping
    _ensure_column(conn, "rides", "cancelled_at", "TEXT")
    _ensure_column(conn, "rides", "cancelled_by", "TEXT")
    _ensure_column(conn, "rides", "cancel_reason", "TEXT DEFAULT ''")
    _ensure_column(conn, "ride_passengers", "cancelled_at", "TEXT")
    _ensure_column(conn, "ride_passengers", "penalty_amount", "REAL NOT NULL DEFAULT 0")
    _allow_penalty_kind(conn)

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
        "CREATE INDEX IF NOT EXISTS idx_reviews_reviewee ON reviews(reviewee_id)",
        "CREATE INDEX IF NOT EXISTS idx_reviews_ride ON reviews(ride_id)",
        "CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_transactions_ride ON transactions(ride_id)",
        "CREATE INDEX IF NOT EXISTS idx_bkash_payments_user ON bkash_payments(user_id)",
        # Idempotency guards: a ride can only ever settle once per user+kind, and a
        # bKash trxID can only ever be credited once (protects against double-clicks
        # and gateway callback retries).
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_ride_leg ON transactions(ride_id, user_id, kind) WHERE ride_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_payment ON transactions(payment_id) WHERE payment_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_bkash_trx ON bkash_payments(trx_id) WHERE trx_id IS NOT NULL",
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

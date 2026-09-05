"""Keep all test imports and API writes away from the demonstration database."""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_database_dir = TemporaryDirectory(prefix="arooohi-tests-")
os.environ["DATABASE_PATH"] = str(Path(_database_dir.name) / "test.db")
os.environ["DEMO_MODE"] = "1"  # Tests must never select an external payment gateway.


def pytest_sessionfinish(session, exitstatus):
    _database_dir.cleanup()

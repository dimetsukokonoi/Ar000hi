"""Executable MVC boundaries and the API contract captured before extraction."""

import ast
import importlib
import json
from pathlib import Path

import pytest
from app.main import app
from app.models import database, rides

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_public_api_contract_is_unchanged():
    baseline = Path(__file__).parent / "fixtures" / "openapi_before_mvc.json"
    assert app.openapi() == json.loads(baseline.read_text())


@pytest.mark.parametrize("layer", ["models", "schemas", "views"])
def test_inner_layers_do_not_depend_on_http_controllers(layer):
    for path in (APP_DIR / layer).glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            for module in modules:
                assert not module.startswith(
                    ("fastapi", "starlette", "app.controllers", "app.routes")
                ), path
                if layer == "models":
                    assert not module.startswith("app.views"), path
                if layer == "views":
                    assert not module.startswith(
                        ("sqlite3", "app.models", "app.database")
                    ), path


def test_controllers_do_not_contain_persistence():
    for path in (APP_DIR / "controllers").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call):
                called = ast.unparse(node.func)
                assert called != "get_db", path
                assert not called.endswith(
                    (
                        ".execute",
                        ".executemany",
                        ".executescript",
                        ".commit",
                        ".rollback",
                    )
                ), path


def test_legacy_imports_point_to_same_implementations():
    for path in (APP_DIR / "routes").glob("*.py"):
        if path.stem == "__init__":
            continue
        legacy = importlib.import_module(f"app.routes.{path.stem}")
        controller = importlib.import_module(f"app.controllers.{path.stem}")
        assert legacy.router is controller.router
    from app.database import get_db
    from app.routes.rides import HOTSPOTS

    assert get_db is database.get_db
    assert HOTSPOTS is rides.HOTSPOTS
    from app.routes.history import _build_pdf
    from app.routes.bkash_checkout import _render
    from app.views import receipts, checkout

    assert _build_pdf is receipts._build_pdf
    assert _render is checkout._render


def test_models_can_be_called_without_a_request_object():
    assert rides.get_hotspots() == rides.HOTSPOTS
    assert "user_id" in __import__("inspect").signature(rides.list_rides).parameters


def test_database_default_still_points_to_backend_directory(monkeypatch):
    # Do not reload the module or initialise the real database.
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    source = ast.parse((APP_DIR / "models" / "database.py").read_text())
    assignment = next(
        n
        for n in source.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "DB_PATH" for t in n.targets)
    )
    import os

    path = eval(
        compile(ast.Expression(assignment.value), "database.py", "eval"),
        {"os": os, "__file__": str(APP_DIR / "models" / "database.py")},
    )
    assert Path(path).resolve() == APP_DIR.parent / "arooohi.db"

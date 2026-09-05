"""Compatibility imports. New HTTP handlers live in app.controllers.history."""
from app.controllers.history import *  # noqa: F401,F403
from app.models import history as _model
from app.views.receipts import _build_pdf, _fmt_dt, _money  # noqa: F401


def __getattr__(name):
    return getattr(_model, name)

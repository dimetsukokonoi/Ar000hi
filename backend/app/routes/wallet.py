"""Compatibility imports. New HTTP handlers live in app.controllers.wallet."""
from app.controllers.wallet import *  # noqa: F401,F403
from app.models import wallet as _model


def __getattr__(name):
    return getattr(_model, name)

"""Compatibility imports. New HTTP handlers live in app.controllers.auth."""
from app.controllers.auth import *  # noqa: F401,F403
from app.models import auth as _model


def __getattr__(name):
    return getattr(_model, name)

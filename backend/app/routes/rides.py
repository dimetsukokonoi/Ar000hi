"""Compatibility imports. New HTTP handlers live in app.controllers.rides."""
from app.controllers.rides import *  # noqa: F401,F403
from app.models import rides as _model


def __getattr__(name):
    return getattr(_model, name)

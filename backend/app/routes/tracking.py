"""Compatibility imports. New HTTP handlers live in app.controllers.tracking."""
from app.controllers.tracking import *  # noqa: F401,F403
from app.models import tracking as _model


def __getattr__(name):
    return getattr(_model, name)

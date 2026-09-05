"""Compatibility imports. New HTTP handlers live in app.controllers.earnings."""
from app.controllers.earnings import *  # noqa: F401,F403
from app.models import earnings as _model


def __getattr__(name):
    return getattr(_model, name)

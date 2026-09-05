"""Compatibility imports. New HTTP handlers live in app.controllers.surge."""
from app.controllers.surge import *  # noqa: F401,F403
from app.models import surge as _model


def __getattr__(name):
    return getattr(_model, name)

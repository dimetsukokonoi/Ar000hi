"""Compatibility imports. New HTTP handlers live in app.controllers.reviews."""
from app.controllers.reviews import *  # noqa: F401,F403
from app.models import reviews as _model


def __getattr__(name):
    return getattr(_model, name)

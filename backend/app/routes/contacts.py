"""Compatibility imports. New HTTP handlers live in app.controllers.contacts."""
from app.controllers.contacts import *  # noqa: F401,F403
from app.models import contacts as _model


def __getattr__(name):
    return getattr(_model, name)

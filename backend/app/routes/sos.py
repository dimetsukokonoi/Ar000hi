"""Compatibility imports. New HTTP handlers live in app.controllers.sos."""
from app.controllers.sos import *  # noqa: F401,F403
from app.models import sos as _model


def __getattr__(name):
    return getattr(_model, name)

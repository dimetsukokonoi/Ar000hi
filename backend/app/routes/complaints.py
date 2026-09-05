"""Compatibility imports. New HTTP handlers live in app.controllers.complaints."""
from app.controllers.complaints import *  # noqa: F401,F403
from app.models import complaints as _model


def __getattr__(name):
    return getattr(_model, name)

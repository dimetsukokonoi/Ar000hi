"""Compatibility imports. New HTTP handlers live in app.controllers.drivers."""
from app.controllers.drivers import *  # noqa: F401,F403
from app.models import drivers as _model


def __getattr__(name):
    return getattr(_model, name)

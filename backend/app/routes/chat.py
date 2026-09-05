"""Compatibility imports for app.controllers.chat."""
from app.controllers.chat import *  # noqa: F401,F403
from app.models import chat as _model

def __getattr__(name):
    return getattr(_model, name)

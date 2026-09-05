"""Compatibility imports for app.controllers.bkash_checkout."""
from app.controllers.bkash_checkout import *  # noqa: F401,F403
from app.models import bkash_checkout as _model
from app.views.checkout import _render, _PAGE, _PINK  # noqa: F401

def __getattr__(name):
    return getattr(_model, name)

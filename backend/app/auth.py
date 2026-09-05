"""Compatibility imports for authentication helpers."""
from app.models.identity import *  # noqa: F401,F403
from app.controllers.dependencies import get_current_user_id, require_admin

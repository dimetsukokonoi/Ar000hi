"""FastAPI dependencies: translate HTTP credentials into a verified identity."""

from fastapi import Request
from app.models import identity
from app.models.errors import DomainError


def get_current_user_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise DomainError(status_code=401, detail="Not authenticated")
    payload = identity.decode_token(auth_header.split(" ")[1])
    user_id = payload.get("sub")
    if not user_id:
        raise DomainError(status_code=401, detail="Invalid token payload")
    return identity.ensure_active_user(user_id)


def require_admin(request: Request) -> str:
    return identity.ensure_admin(get_current_user_id(request))

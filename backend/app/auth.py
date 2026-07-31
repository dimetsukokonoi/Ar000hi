"""
Arooohi Backend — Auth Utilities (JWT + Password Hashing)
Uses bcrypt directly (passlib has compat issues with bcrypt 5.x)
"""
import os
import warnings
from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt
from fastapi import HTTPException, Request

SECRET_KEY = os.getenv("SECRET_KEY", "arooohi-dev-secret-key-2024")
if SECRET_KEY == "arooohi-dev-secret-key-2024":
    # Security improvement (PROJECT_PLAN.md §6.1): never silently run on the
    # well-known default outside of a local demo. Fail fast in production.
    if os.getenv("DEMO_MODE", "1") != "1":
        raise RuntimeError(
            "SECRET_KEY env var must be set when DEMO_MODE != 1 (refusing to use the default secret)"
        )
    warnings.warn(
        "Using the DEFAULT demo SECRET_KEY. Set SECRET_KEY (and DEMO_MODE=0) for anything beyond local testing.",
        stacklevel=2,
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user_id(request: Request) -> str:
    """Extract user ID from the Authorization header, and ensure the account is
    still active (fix for PROJECT_PLAN.md §6.1: deactivated/deleted users used to
    keep working tokens)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header.split(" ")[1]
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    from app.database import get_db
    conn = get_db()
    user = conn.execute(
        "SELECT is_active FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Your account has been deactivated")
    return user_id


def require_admin(request: Request) -> str:
    """Ensure the current user is an admin."""
    from app.database import get_db
    user_id = get_current_user_id(request)
    conn = get_db()
    user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id

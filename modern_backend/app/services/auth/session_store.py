import secrets
from datetime import datetime, timedelta

# Simple in-memory session store (in production, use Redis)
SESSIONS: dict[str, dict] = {}
SESSION_TIMEOUT = 30 * 60  # 30 minutes


def create_session(
    employee_id: int,
    employee_name: str,
    role: str = "user",
    permissions: dict | None = None,
    username: str | None = None,
) -> str:
    """Create and store a session token."""
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "employee_id": employee_id,
        "name": employee_name,
        "username": username or employee_name,
        "role": role,
        "permissions": permissions or {},
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(seconds=SESSION_TIMEOUT),
    }
    return token


def get_session(token: str | None) -> dict | None:
    """Retrieve session if valid and refresh expiration."""
    if not token or token not in SESSIONS:
        return None

    session = SESSIONS[token]
    if datetime.now() > session["expires_at"]:
        del SESSIONS[token]
        return None

    # Sliding expiration for active sessions.
    session["expires_at"] = datetime.now() + timedelta(seconds=SESSION_TIMEOUT)
    return session


def revoke_session(token: str | None) -> None:
    if token and token in SESSIONS:
        del SESSIONS[token]


def parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None

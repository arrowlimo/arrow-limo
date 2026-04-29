"""Shared session auth helpers for API middleware and role checks."""

from fastapi import HTTPException, Request, status

from .routers.driver_auth import get_session, parse_bearer_token

PROTECTED_PATH_PREFIXES = (
    "/api",
    "/banking",
    "/receipts",
)
AUTH_EXEMPT_PATHS = {
    "/health",
    "/db-ping",
}
AUTH_EXEMPT_PREFIXES = (
    "/auth",
    "/api/inspection-forms",
)


def _matches_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}/")


def is_protected_path(path: str) -> bool:
    return any(
        _matches_prefix(path, prefix) for prefix in PROTECTED_PATH_PREFIXES
    )


def is_auth_exempt_path(path: str) -> bool:
    if path in AUTH_EXEMPT_PATHS:
        return True
    return any(
        _matches_prefix(path, prefix) for prefix in AUTH_EXEMPT_PREFIXES
    )


def resolve_authenticated_user(request: Request) -> dict | None:
    authorization = request.headers.get("Authorization")
    session_token = parse_bearer_token(authorization) or request.cookies.get(
        "session_token"
    )
    if not session_token:
        return None

    session = get_session(session_token)
    if not session:
        return None

    return {
        "user_id": session["employee_id"],
        "employee_id": session["employee_id"],
        "username": session.get("username") or session["name"],
        "name": session["name"],
        "role": session.get("role", "user"),
        "permissions": session.get("permissions", {}),
    }


def get_current_user(request: Request) -> dict:
    user = getattr(request.state, "current_user", None)
    if user:
        return user

    user = resolve_authenticated_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    request.state.current_user = user
    return user


def require_roles(*allowed_roles: str):
    allowed = {role for role in allowed_roles}

    def dependency(request: Request) -> dict:
        user = get_current_user(request)
        if user.get("role") not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges",
            )
        return user

    return dependency

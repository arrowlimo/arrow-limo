"""Shared session auth helpers for API middleware and role checks."""

from fastapi import HTTPException, Request, status

from .services.auth.session_store import get_session, parse_bearer_token

PROTECTED_PATH_PREFIXES = (
    "/api",
    "/banking",
    "/receipts",
)
AUTH_EXEMPT_PATHS = {
    "/health",
}
AUTH_EXEMPT_PREFIXES = (
    "/auth",
    "/api/inspection-forms",
)

ROLE_MODULES = {
    "admin": {"*"},
    "super_user": {"*"},
    "manager": {"*"},
    "dispatch": {"dispatch"},
    "dispatcher": {"dispatch"},
    "accountant": {"accounting"},
    "driver": {"chauffeur_self_service"},
    "operator": {"chauffeur_self_service"},
}


def _normalize_role(raw_role: str | None) -> str:
    role = (raw_role or "user").strip().lower()
    aliases = {
        "superuser": "super_user",
    }
    return aliases.get(role, role)


def _permission_modules(permissions: dict | None) -> set[str]:
    perms = permissions or {}
    modules: set[str] = set()

    configured = perms.get("modules")
    if isinstance(configured, list):
        for module in configured:
            if isinstance(module, str) and module.strip():
                modules.add(module.strip())

    for key, value in perms.items():
        if value is True and isinstance(key, str):
            modules.add(key)

    return modules


def has_module_access(user: dict, module: str) -> bool:
    normalized_module = module.strip()
    role = _normalize_role(user.get("role"))

    role_modules = ROLE_MODULES.get(role, set())
    if "*" in role_modules or normalized_module in role_modules:
        return True

    granted_modules = _permission_modules(user.get("permissions"))
    return "*" in granted_modules or normalized_module in granted_modules


def _matches_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}/")


def is_protected_path(path: str) -> bool:
    return any(_matches_prefix(path, prefix) for prefix in PROTECTED_PATH_PREFIXES)


def is_auth_exempt_path(path: str) -> bool:
    if path in AUTH_EXEMPT_PATHS:
        return True
    return any(_matches_prefix(path, prefix) for prefix in AUTH_EXEMPT_PREFIXES)


def resolve_authenticated_user(request: Request) -> dict | None:
    authorization = request.headers.get("Authorization")
    session_token = parse_bearer_token(authorization) or request.cookies.get("session_token")
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
        "role": _normalize_role(session.get("role", "user")),
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
    allowed = {_normalize_role(role) for role in allowed_roles}

    def dependency(request: Request) -> dict:
        user = get_current_user(request)
        if _normalize_role(user.get("role")) not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges",
            )
        return user

    return dependency


def require_any_modules(*modules: str):
    required = {module.strip() for module in modules if module.strip()}

    def dependency(request: Request) -> dict:
        user = get_current_user(request)
        if not required:
            return user
        if any(has_module_access(user, module) for module in required):
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Module access denied",
        )

    return dependency

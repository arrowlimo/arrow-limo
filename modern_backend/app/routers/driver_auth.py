"""
User authentication routes - supports any user role (admin, driver, manager,
super_user, etc.)
Serves login page and handles login for all user types
Last updated: 2026-02-07 - Added auto-login support for local development
"""

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from ..services.auth.audit import record_auth_event
from ..services.auth.credentials import verify_user_credentials
from ..services.auth.dashboard import generate_dashboard_content
from ..services.auth.driver_data import get_driver_trips, get_employee_role
from ..services.auth.session_store import (
    SESSION_TIMEOUT,
    create_session,
    get_session,
    parse_bearer_token,
    revoke_session,
)
from ..settings import get_settings

router = APIRouter(prefix="/auth", tags=["user_auth"])
LOGIN_PATH = "/login"
INVALID_CREDENTIALS = "Invalid credentials"
logger = logging.getLogger("modern_backend.auth")
DRIVER_ROLES = {"driver", "operator"}


def _require_driver_account(user: dict) -> dict:
    if str(user.get("role") or "").strip().lower() not in DRIVER_ROLES:
        raise HTTPException(status_code=403, detail="Driver portal access only")
    return user


def _auto_login_allowed(request: Request) -> bool:
    settings = get_settings()
    legacy_auto_login = os.getenv("AUTO_LOGIN", "false").strip().lower() in {
        "true",
        "1",
        "yes",
    }
    if legacy_auto_login and not settings.enable_auto_login:
        logger.warning(
            "AUTO_LOGIN is deprecated and ignored; set ALMS_ENABLE_AUTO_LOGIN=1 for local dev"
        )

    if not settings.enable_auto_login:
        return False

    if settings.environment.strip().lower() not in {"development", "dev", "local"}:
        return False

    client_host = (request.client.host if request.client else "") or ""
    normalized = client_host.strip().lower()
    if normalized.startswith("127."):
        return True
    return normalized in {"127.0.0.1", "::1", "localhost", "0.0.0.0", "testclient"}


class LoginRequest(BaseModel):
    username: str
    password: str


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Route browser login requests to the SPA login page."""
    session_token = request.cookies.get("session_token")
    if session_token and get_session(session_token):
        return RedirectResponse(url="/", status_code=302)
    return RedirectResponse(url=LOGIN_PATH, status_code=302)


@router.get("/auto-login-check")
async def auto_login_check(request: Request):
    """Never bypass credentials in the driver-only web portal."""
    if _auto_login_allowed(request):
        logger.warning("Blocked auto-login for the driver-only portal")
    return JSONResponse({"auto_login": False})


@router.post("/login-submit", responses={401: {"description": "Invalid credentials"}})
async def login_submit(
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    request: Request = None,
    response: Response = None,
):
    """Handle login form submission (HTML form)"""
    user = verify_user_credentials(username, password)
    if not user:
        record_auth_event(
            action="login_failed",
            username=username,
            user_id=None,
            role=None,
            request=request,
            note=INVALID_CREDENTIALS,
        )
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    _require_driver_account(user)
    session_token = create_session(
        user["employee_id"],
        user["name"],
        role=user.get("role", "user"),
        permissions=user.get("permissions", {}),
        username=username,
    )
    response.set_cookie(
        key="session_token",
        value=session_token,
        max_age=30 * 60,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    record_auth_event(
        action="login_succeeded",
        username=username,
        user_id=user.get("employee_id"),
        role=user.get("role", "user"),
        request=request,
        note="HTML login",
    )
    return {"status": "success", "redirect": "/auth/dashboard"}


@router.post("/login", responses={401: {"description": "Invalid credentials"}})
async def login_json(login_request: LoginRequest, request: Request):
    """Handle JSON login (for Vue frontend)"""
    logger.info("Login attempt via JSON endpoint")
    user = verify_user_credentials(login_request.username, login_request.password)
    if not user:
        logger.warning("Login failed via JSON endpoint")
        record_auth_event(
            action="login_failed",
            username=login_request.username,
            user_id=None,
            role=None,
            request=request,
            note=INVALID_CREDENTIALS,
        )
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    _require_driver_account(user)

    logger.info("Login succeeded via JSON endpoint")
    # Create session token
    session_token = create_session(
        user["employee_id"],
        user["name"],
        role=user.get("role", "user"),
        permissions=user.get("permissions", {}),
        username=login_request.username,
    )
    record_auth_event(
        action="login_succeeded",
        username=login_request.username,
        user_id=user.get("employee_id"),
        role=user.get("role", "user"),
        request=request,
        note="JSON login",
    )

    # Return JWT-style response for frontend
    return {
        "access_token": session_token,
        "token_type": "bearer",
        "expires_in": SESSION_TIMEOUT,
        "user": {
            "user_id": user["employee_id"],
            "username": login_request.username,
            "name": user["name"],
            "role": user.get("role", "user"),
            "permissions": user.get("permissions", {}),
        },
    }


@router.get("/validate", responses={401: {"description": "Invalid or expired token"}})
async def validate_token(request: Request):
    """Validate bearer token for SPA route/API guards."""
    authorization = request.headers.get("Authorization")
    token = parse_bearer_token(authorization)
    session = get_session(token) if token else None
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    _require_driver_account(session)

    return {
        "authenticated": True,
        "expires_at": session["expires_at"].isoformat(),
        "user": {
            "user_id": session["employee_id"],
            "username": session.get("username") or session["name"],
            "name": session["name"],
            "role": session.get("role", "user"),
            "permissions": session.get("permissions", {}),
        },
    }


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """User dashboard - shows different content based on role"""
    session_token = request.cookies.get("session_token")
    session = get_session(session_token)
    if not session:
        return RedirectResponse(url=LOGIN_PATH, status_code=302)

    employee_id = session["employee_id"]
    user_name = session["name"]

    user_role = get_employee_role(employee_id)
    trips = get_driver_trips(employee_id) if user_role in ["driver", "operator"] else []
    return generate_dashboard_content(user_name, user_role, trips)


@router.get("/logout")
async def logout(response: Response):
    """Logout user and clear session"""
    response.delete_cookie("session_token")
    return RedirectResponse(url=LOGIN_PATH, status_code=302)


@router.post("/logout")
async def logout_json(request: Request):
    """API logout for SPA clients using bearer token."""
    authorization = request.headers.get("Authorization")
    token = parse_bearer_token(authorization)
    session = get_session(token) if token else None
    revoke_session(token)
    record_auth_event(
        action="logout",
        username=(session or {}).get("username"),
        user_id=(session or {}).get("employee_id"),
        role=(session or {}).get("role"),
        request=request,
        note="Bearer token logout",
    )
    return {"status": "ok"}

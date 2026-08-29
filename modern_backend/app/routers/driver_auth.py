import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from ..audit.engine import ensure_audit_storage
from ..auth import SUPPORT_SESSION_ROLE
from ..db import get_connection, return_connection
from ..services.auth.audit import record_auth_event
from ..services.auth.credentials import (
    get_user_by_id,
    hash_password,
    replace_password,
    verify_password,
    verify_user_credentials,
)
from ..services.auth.onboarding import (
    create_mfa_challenge,
    create_onboarding_challenge,
    ensure_auth_tables,
    get_linked_employee_phone,
    issue_phone_code,
    mark_phone_verified,
    mask_phone,
    require_challenge,
    require_enrollment_phone,
    set_challenge_purpose,
    verify_phone_code,
)
from ..services.auth.session_store import (
    SESSION_TIMEOUT,
    create_impersonated_session,
    create_session,
    get_session,
    parse_bearer_token,
    revoke_session,
)
from ..settings import get_settings

router = APIRouter(prefix="/auth", tags=["driver_auth"])
LOGIN_PATH = "/login"
INVALID_CREDENTIALS = "Invalid credentials"
DRIVER_ROLES = {"driver", "operator"}
SUPPORT_ACCOUNT_ROLES = {"admin", "super_user", "superuser"}
SUPPORT_SESSION_ROLES = {SUPPORT_SESSION_ROLE}
logger = logging.getLogger("modern_backend.auth")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=255)


class PasswordChangeRequest(BaseModel):
    challenge_token: str = Field(min_length=20, max_length=255)
    new_password: str = Field(min_length=12, max_length=255)


class PhoneEnrollmentRequest(BaseModel):
    challenge_token: str = Field(min_length=20, max_length=255)
    phone: str = Field(min_length=10, max_length=30)


class CodeVerificationRequest(BaseModel):
    challenge_token: str = Field(min_length=20, max_length=255)
    code: str = Field(pattern=r"^\d{6}$")


class ChallengeRequest(BaseModel):
    challenge_token: str = Field(min_length=20, max_length=255)


class SupportImpersonationRequest(BaseModel):
    employee_id: int = Field(gt=0)


class SupportPasswordResetRequest(BaseModel):
    employee_id: int = Field(gt=0)
    temporary_password: str = Field(min_length=12, max_length=255)


def _require_driver_account(user: dict) -> dict:
    if str(user.get("role") or "").strip().lower() not in DRIVER_ROLES:
        raise HTTPException(status_code=403, detail="Driver portal access only")
    if user.get("employee_id") is None:
        raise HTTPException(status_code=403, detail="Driver account is not linked")
    return user


def _user_response(user: dict) -> dict:
    return {
        "user_id": user.get("account_id") or user.get("auth_user_id") or user.get("employee_id"),
        "employee_id": user.get("employee_id"),
        "username": user["username"],
        "name": user["name"],
        "role": user.get("role", "driver"),
        "permissions": user.get("permissions", {}),
        "impersonated_by": user.get("impersonated_by") or user.get("impersonator_username"),
    }


def _authenticated_response(user: dict) -> dict:
    token = create_session(
        user["employee_id"],
        user["name"],
        role=user.get("role", "driver"),
        permissions=user.get("permissions", {}),
        username=user["username"],
        auth_user_id=user.get("account_id"),
    )
    return {
        "next_step": "complete",
        "access_token": token,
        "token_type": "bearer",
        "expires_in": SESSION_TIMEOUT,
        "user": _user_response(user),
    }


def _authenticated_support_response(user: dict) -> dict:
    permissions = {"modules": ["support_impersonation"]}
    token = create_session(
        None,
        user["name"],
        role=SUPPORT_SESSION_ROLE,
        permissions=permissions,
        username=user["username"],
        auth_user_id=user["account_id"],
    )
    response_user = {
        **user,
        "employee_id": None,
        "role": SUPPORT_SESSION_ROLE,
        "permissions": permissions,
    }
    return {
        "next_step": "complete",
        "access_token": token,
        "token_type": "bearer",
        "expires_in": SESSION_TIMEOUT,
        "user": _user_response(response_user),
        "support_mode": True,
    }


def _require_support_session(request: Request) -> dict:
    token = parse_bearer_token(request.headers.get("Authorization"))
    session = get_session(token)
    role = str(session.get("role") if session else "").strip().lower()
    if not session or role not in SUPPORT_SESSION_ROLES or not session.get("auth_user_id"):
        raise HTTPException(status_code=403, detail="Administrator support access required")
    return session


def _sms_mfa_ready() -> bool:
    settings = get_settings()
    return bool(
        settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number
    )


@router.get("/login")
async def login_page():
    return RedirectResponse(url=LOGIN_PATH, status_code=302)


@router.get("/auto-login-check")
async def auto_login_check():
    return JSONResponse({"auto_login": False})


@router.post("/login-submit")
async def login_submit_disabled():
    raise HTTPException(status_code=410, detail="Use the driver portal login")


@router.post("/login", responses={401: {"description": "Invalid credentials"}})
async def login_json(payload: LoginRequest, request: Request):
    user = verify_user_credentials(payload.username, payload.password)
    if not user:
        record_auth_event(
            action="login_failed",
            username=payload.username,
            user_id=None,
            role=None,
            request=request,
            note=INVALID_CREDENTIALS,
        )
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    role = str(user.get("role") or "").strip().lower()
    if role in SUPPORT_ACCOUNT_ROLES:
        record_auth_event(
            action="support_login",
            username=user["username"],
            user_id=user["account_id"],
            role=role,
            request=request,
            note="Restricted driver support session opened",
        )
        return _authenticated_support_response(user)
    _require_driver_account(user)

    if not _sms_mfa_ready():
        raise HTTPException(
            status_code=503,
            detail="SMS verification is temporarily unavailable",
        )
    if user["must_change_password"]:
        challenge_token = create_onboarding_challenge(user["account_id"], purpose="activation")
        phone = issue_phone_code(
            challenge_token,
            user["account_id"],
            get_linked_employee_phone(user["account_id"]),
            "activation",
        )
        return {
            "next_step": "verify_activation",
            "challenge_token": challenge_token,
            "masked_phone": mask_phone(phone),
            "user": _user_response(user),
        }
    if not user["phone_verified"] or not user["mfa_phone"]:
        return {
            "next_step": "enroll_phone",
            "challenge_token": create_onboarding_challenge(
                user["account_id"], purpose="enroll_phone"
            ),
            "user": _user_response(user),
        }

    challenge_token, phone = create_mfa_challenge(user["account_id"], user["mfa_phone"])
    record_auth_event(
        action="mfa_challenge_sent",
        username=user["username"],
        user_id=user["employee_id"],
        role=user["role"],
        request=request,
        note="SMS verification required",
    )
    return {
        "next_step": "verify_mfa",
        "challenge_token": challenge_token,
        "masked_phone": mask_phone(phone),
        "user": _user_response(user),
    }


@router.post("/change-password")
async def change_password(payload: PasswordChangeRequest, request: Request):
    user_id, _, _ = require_challenge(payload.challenge_token, {"onboarding"})
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Login challenge expired")
    if verify_password(payload.new_password, _password_hash_for_user(user_id)):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the temporary password",
        )
    _validate_new_password(payload.new_password)
    replace_password(user_id, payload.new_password)
    refreshed_user = get_user_by_id(user_id)
    if not refreshed_user:
        raise HTTPException(status_code=401, detail="Driver account not found")
    record_auth_event(
        action="password_changed",
        username=refreshed_user["username"],
        user_id=refreshed_user["employee_id"],
        role=refreshed_user["role"],
        request=request,
        note="Driver changed the pending first-login password",
    )
    if refreshed_user["phone_verified"] and refreshed_user["mfa_phone"]:
        return _authenticated_response(refreshed_user)
    set_challenge_purpose(payload.challenge_token, user_id, "enroll_phone")
    return {"next_step": "enroll_phone", "challenge_token": payload.challenge_token}


def _password_hash_for_user(user_id: int):
    from ..db import get_connection, return_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM users WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
        return row[0] if row else None
    finally:
        return_connection(conn)


def _validate_new_password(password: str) -> None:
    if not (
        any(char.islower() for char in password)
        and any(char.isupper() for char in password)
        and any(char.isdigit() for char in password)
    ):
        raise HTTPException(
            status_code=400,
            detail="Password must contain upper-case, lower-case, and number characters",
        )


@router.post("/enroll-phone")
async def enroll_phone(payload: PhoneEnrollmentRequest):
    user_id, _, _ = require_challenge(payload.challenge_token, {"enroll_phone", "phone_verify"})
    phone = require_enrollment_phone(user_id, payload.phone)
    phone = issue_phone_code(payload.challenge_token, user_id, phone, "phone_verify")
    return {
        "next_step": "verify_phone",
        "challenge_token": payload.challenge_token,
        "masked_phone": mask_phone(phone),
    }


@router.post("/resend-code")
async def resend_code(payload: ChallengeRequest):
    user_id, purpose, phone = require_challenge(
        payload.challenge_token, {"activation", "phone_verify", "mfa"}
    )
    if not phone:
        raise HTTPException(status_code=400, detail="Mobile phone is required")
    phone = issue_phone_code(payload.challenge_token, user_id, phone, purpose)
    return {
        "next_step": (
            "verify_activation"
            if purpose == "activation"
            else "verify_phone"
            if purpose == "phone_verify"
            else "verify_mfa"
        ),
        "challenge_token": payload.challenge_token,
        "masked_phone": mask_phone(phone),
    }


@router.post("/verify-code")
async def verify_code(payload: CodeVerificationRequest, request: Request):
    user_id, purpose, phone = verify_phone_code(payload.challenge_token, payload.code)
    if purpose == "activation":
        mark_phone_verified(user_id, phone)
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="Driver account not found")
        _require_driver_account(user)
        record_auth_event(
            action="activation_mfa_verified",
            username=user["username"],
            user_id=user["employee_id"],
            role=user["role"],
            request=request,
            note="First-login phone verification completed",
        )
        return {
            "next_step": "change_password",
            "challenge_token": create_onboarding_challenge(user_id),
            "user": _user_response(user),
        }
    if purpose == "phone_verify":
        mark_phone_verified(user_id, phone)
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Driver account not found")
    _require_driver_account(user)
    record_auth_event(
        action="mfa_verified",
        username=user["username"],
        user_id=user["employee_id"],
        role=user["role"],
        request=request,
        note="Phone verification completed",
    )
    return _authenticated_response(user)


@router.get("/support/employees")
async def list_support_employees(request: Request):
    support = _require_support_session(request)
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    l.employee_id,
                    TRIM(COALESCE(e.first_name, '') || ' ' || COALESCE(e.last_name, '')),
                    u.username,
                    COALESCE(e.employee_category, ''),
                    COALESCE(e.employment_status, e.status, 'active')
                FROM driver_user_links l
                JOIN users u ON u.user_id = l.user_id
                JOIN employees e ON e.employee_id = l.employee_id
                WHERE LOWER(COALESCE(u.role, '')) IN ('driver', 'operator')
                  AND LOWER(COALESCE(u.status, 'active')) = 'active'
                  AND LOWER(COALESCE(e.employment_status, e.status, 'active')) = 'active'
                ORDER BY e.last_name, e.first_name, l.employee_id
                """
            )
            rows = cur.fetchall()
        return {
            "support_user": support["username"],
            "items": [
                {
                    "employee_id": row[0],
                    "name": row[1] or row[2],
                    "username": row[2],
                    "employee_type": row[3],
                    "status": row[4],
                }
                for row in rows
            ],
        }
    finally:
        return_connection(conn)


@router.get("/support/notifications")
async def list_support_notifications(request: Request):
    _require_support_session(request)
    conn = get_connection()
    try:
        ensure_audit_storage(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT occurred_at, action, actor_json->>'username', note
                FROM audit_events
                WHERE module = 'driver_auth'
                  AND (
                    action IN (
                        'login_failed',
                        'password_changed',
                        'support_login',
                        'support_pending_password_reset',
                        'support_impersonation_started'
                    )
                    OR action LIKE 'support_impersonated_%'
                  )
                ORDER BY occurred_at DESC
                LIMIT 50
                """
            )
            rows = cur.fetchall()

        def notification(row):
            action = row[1]
            username = row[2] or "Unknown account"
            messages = {
                "login_failed": f"Failed login attempt for {username}",
                "password_changed": f"{username} changed their password",
                "support_login": f"{username} opened Admin Driver Access",
                "support_pending_password_reset": (
                    f"{username} reset a pending driver login password"
                ),
                "support_impersonation_started": f"{username} opened a driver account",
            }
            return {
                "occurred_at": row[0].isoformat(),
                "action": action,
                "severity": "warning"
                if action in {"login_failed", "support_pending_password_reset"}
                else "info",
                "message": messages.get(
                    action,
                    f"{username} changed a driver record through Admin Driver Access",
                ),
                "detail": row[3],
            }

        return {"items": [notification(row) for row in rows]}
    finally:
        return_connection(conn)


@router.post("/support/impersonate")
async def impersonate_driver(
    payload: SupportImpersonationRequest,
    request: Request,
):
    _require_support_session(request)
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    u.user_id,
                    l.employee_id,
                    u.username,
                    COALESCE(
                        NULLIF(TRIM(COALESCE(e.first_name, '') || ' ' || COALESCE(e.last_name, '')), ''),
                        u.username
                    ),
                    u.role,
                    u.permissions
                FROM driver_user_links l
                JOIN users u ON u.user_id = l.user_id
                JOIN employees e ON e.employee_id = l.employee_id
                WHERE l.employee_id = %s
                  AND LOWER(COALESCE(u.role, '')) IN ('driver', 'operator')
                  AND LOWER(COALESCE(u.status, 'active')) = 'active'
                  AND LOWER(COALESCE(e.employment_status, e.status, 'active')) = 'active'
                LIMIT 1
                """,
                (payload.employee_id,),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Active driver account not found")
        permissions = row[5] if isinstance(row[5], dict) else {}
        session_result = create_impersonated_session(
            parse_bearer_token(request.headers.get("Authorization")),
            employee_id=row[1],
            employee_name=row[3],
            role=row[4],
            permissions=permissions,
            username=row[2],
            auth_user_id=row[0],
            allowed_support_roles=SUPPORT_SESSION_ROLES,
        )
        if not session_result:
            raise HTTPException(status_code=403, detail="Administrator support access required")
        token, support = session_result
        record_auth_event(
            action="support_impersonation_started",
            username=support["username"],
            user_id=support["auth_user_id"],
            role=support["role"],
            request=request,
            note=f"Driver employee_id={row[1]} opened for support",
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": SESSION_TIMEOUT,
            "user": {
                "user_id": row[0],
                "employee_id": row[1],
                "username": row[2],
                "name": row[3],
                "role": row[4],
                "permissions": permissions,
                "impersonated_by": support["username"],
            },
        }
    finally:
        return_connection(conn)


@router.post("/support/reset-pending-password")
async def reset_pending_driver_password(
    payload: SupportPasswordResetRequest,
    request: Request,
):
    support = _require_support_session(request)
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users u
                SET password_hash = %s,
                    failed_login_attempts = 0,
                    locked_until = NULL,
                    session_version = COALESCE(session_version, 1) + 1,
                    updated_at = NOW()
                FROM driver_user_links l
                JOIN driver_auth_state s ON s.user_id = l.user_id
                JOIN employees e ON e.employee_id = l.employee_id
                WHERE u.user_id = l.user_id
                  AND l.employee_id = %s
                  AND s.must_change_password = TRUE
                  AND LOWER(COALESCE(u.role, '')) IN ('driver', 'operator')
                  AND LOWER(COALESCE(u.status, 'active')) = 'active'
                  AND LOWER(COALESCE(e.employment_status, e.status, 'active')) = 'active'
                RETURNING u.user_id, u.username
                """,
                (hash_password(payload.temporary_password), payload.employee_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=409,
                    detail="Only a pending first-login account can be reset",
                )
            cur.execute(
                "DELETE FROM driver_auth_challenges WHERE user_id = %s",
                (row[0],),
            )
            cur.execute(
                """
                UPDATE web_sessions
                SET revoked_at = NOW()
                WHERE employee_id = %s AND revoked_at IS NULL
                """,
                (payload.employee_id,),
            )
        conn.commit()
        record_auth_event(
            action="support_pending_password_reset",
            username=support["username"],
            user_id=support["auth_user_id"],
            role=support["role"],
            request=request,
            note=f"Pending password reset for employee_id={payload.employee_id}",
        )
        return {"status": "reset", "username": row[1]}
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


@router.get("/validate", responses={401: {"description": "Invalid or expired token"}})
async def validate_token(request: Request):
    token = parse_bearer_token(request.headers.get("Authorization"))
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    role = str(session.get("role") or "").strip().lower()
    if role not in SUPPORT_SESSION_ROLES:
        _require_driver_account(session)
    return {
        "authenticated": True,
        "expires_at": session["expires_at"].isoformat(),
        "user": _user_response(session),
    }


@router.post("/logout")
async def logout_json(request: Request):
    revoke_session(parse_bearer_token(request.headers.get("Authorization")))
    return {"status": "success"}

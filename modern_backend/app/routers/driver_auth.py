import logging

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from ..services.auth.audit import record_auth_event
from ..services.auth.credentials import (
    get_user_by_id,
    replace_password,
    verify_password,
    verify_user_credentials,
)
from ..services.auth.onboarding import (
    create_mfa_challenge,
    create_onboarding_challenge,
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


def _require_driver_account(user: dict) -> dict:
    if str(user.get("role") or "").strip().lower() not in DRIVER_ROLES:
        raise HTTPException(status_code=403, detail="Driver portal access only")
    if user.get("employee_id") is None:
        raise HTTPException(status_code=403, detail="Driver account is not linked")
    return user


def _user_response(user: dict) -> dict:
    return {
        "user_id": user["employee_id"],
        "username": user["username"],
        "name": user["name"],
        "role": user.get("role", "driver"),
        "permissions": user.get("permissions", {}),
    }


def _authenticated_response(user: dict) -> dict:
    token = create_session(
        user["employee_id"],
        user["name"],
        role=user.get("role", "driver"),
        permissions=user.get("permissions", {}),
        username=user["username"],
    )
    return {
        "next_step": "complete",
        "access_token": token,
        "token_type": "bearer",
        "expires_in": SESSION_TIMEOUT,
        "user": _user_response(user),
    }


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
async def change_password(payload: PasswordChangeRequest):
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


@router.get("/validate", responses={401: {"description": "Invalid or expired token"}})
async def validate_token(request: Request):
    token = parse_bearer_token(request.headers.get("Authorization"))
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    _require_driver_account(session)
    return {
        "authenticated": True,
        "expires_at": session["expires_at"].isoformat(),
        "user": _user_response(session),
    }


@router.get("/logout")
async def logout(response: Response):
    response.delete_cookie("session_token")
    return RedirectResponse(url=LOGIN_PATH, status_code=302)


@router.post("/logout")
async def logout_json(request: Request):
    revoke_session(parse_bearer_token(request.headers.get("Authorization")))
    return {"status": "success"}

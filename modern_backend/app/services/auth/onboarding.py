import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from threading import Lock

import requests
from fastapi import HTTPException

from ...db import get_connection, return_connection
from ...settings import get_settings

CHALLENGE_MINUTES = 15
OTP_MINUTES = 10
_AUTH_TABLES_READY = False
_AUTH_TABLES_LOCK = Lock()


def ensure_auth_tables(conn) -> None:
    global _AUTH_TABLES_READY
    if _AUTH_TABLES_READY:
        return
    with _AUTH_TABLES_LOCK:
        if _AUTH_TABLES_READY:
            return
        with conn.cursor() as cur:
            cur.execute(
                """
            CREATE TABLE IF NOT EXISTS driver_auth_state (
                user_id INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
                must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
                mfa_phone VARCHAR(20) NULL,
                phone_verified_at TIMESTAMPTZ NULL,
                password_changed_at TIMESTAMPTZ NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS driver_user_links (
                    user_id INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
                    employee_id INTEGER NOT NULL UNIQUE
                        REFERENCES employees(employee_id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
            CREATE TABLE IF NOT EXISTS driver_auth_challenges (
                challenge_hash CHAR(64) PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                purpose VARCHAR(32) NOT NULL,
                otp_hash CHAR(64) NULL,
                pending_phone VARCHAR(20) NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 5,
                send_count INTEGER NOT NULL DEFAULT 0,
                last_sent_at TIMESTAMPTZ NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_driver_auth_challenges_expiry
                ON driver_auth_challenges (expires_at)
                """
            )
            cur.execute(
                """
                ALTER TABLE driver_auth_challenges
                ADD COLUMN IF NOT EXISTS send_count INTEGER NOT NULL DEFAULT 0
                """
            )
            cur.execute(
                """
                ALTER TABLE driver_auth_challenges
                ADD COLUMN IF NOT EXISTS last_sent_at TIMESTAMPTZ NULL
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS driver_sms_rate_limits (
                    user_id INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
                    window_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    send_count INTEGER NOT NULL DEFAULT 0,
                    last_sent_at TIMESTAMPTZ NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS web_sessions (
                    token_hash CHAR(64) PRIMARY KEY,
                    employee_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    permissions JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMPTZ NOT NULL,
                    revoked_at TIMESTAMPTZ NULL
                )
                """
            )
        conn.commit()
        _AUTH_TABLES_READY = True


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _otp_hash(challenge_token: str, code: str) -> str:
    return _hash(f"{challenge_token}:{code}")


def normalize_phone(phone: str) -> str:
    stripped = phone.strip()
    has_plus = stripped.startswith("+")
    digits = re.sub(r"\D", "", stripped)
    if len(digits) == 10:
        digits = f"1{digits}"
    if len(digits) < 11 or len(digits) > 15:
        raise HTTPException(status_code=400, detail="Enter a valid mobile phone number")
    return f"+{digits}" if has_plus or digits else digits


def mask_phone(phone: str) -> str:
    return f"••• ••• {phone[-4:]}"


def require_enrollment_phone(user_id: int, submitted_phone: str) -> str:
    normalized = normalize_phone(submitted_phone)
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.cell_phone, e.phone
                FROM driver_user_links l
                JOIN employees e ON e.employee_id = l.employee_id
                WHERE l.user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=409, detail="Driver account is not linked")
        recorded = set()
        for candidate in row:
            if not candidate:
                continue
            try:
                recorded.add(normalize_phone(candidate))
            except HTTPException:
                continue
        if not recorded:
            raise HTTPException(
                status_code=409,
                detail="Ask the office to add your mobile number to your employee file",
            )
        if normalized not in recorded:
            raise HTTPException(
                status_code=400,
                detail="Phone number does not match your employee file",
            )
        return normalized
    finally:
        return_connection(conn)


def get_linked_employee_phone(user_id: int) -> str:
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.cell_phone, e.phone
                FROM driver_user_links l
                JOIN employees e ON e.employee_id = l.employee_id
                WHERE l.user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=409, detail="Driver account is not linked")
        for candidate in row:
            if not candidate:
                continue
            try:
                return normalize_phone(candidate)
            except HTTPException:
                continue
        raise HTTPException(
            status_code=409,
            detail="Ask the office to add your mobile number to your employee file",
        )
    finally:
        return_connection(conn)


def _send_sms(phone: str, code: str) -> None:
    settings = get_settings()
    if not all(
        (
            settings.twilio_account_sid,
            settings.twilio_auth_token,
            settings.twilio_from_number,
        )
    ):
        raise HTTPException(status_code=503, detail="SMS verification is not configured")
    response = requests.post(
        (f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"),
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        data={
            "To": phone,
            "From": settings.twilio_from_number,
            "Body": f"Your Arrow Limousine driver portal verification code is {code}.",
        },
        timeout=15,
    )
    if not response.ok:
        raise HTTPException(status_code=503, detail="Unable to send verification code")


def create_onboarding_challenge(user_id: int, purpose: str = "onboarding") -> str:
    if purpose not in {"activation", "onboarding", "enroll_phone"}:
        raise ValueError("Invalid onboarding challenge purpose")
    token = secrets.token_urlsafe(32)
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM driver_auth_challenges WHERE expires_at < NOW() OR user_id = %s",
                (user_id,),
            )
            cur.execute(
                """
                INSERT INTO driver_auth_challenges (
                    challenge_hash, user_id, purpose, expires_at
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    _hash(token),
                    user_id,
                    purpose,
                    datetime.now(timezone.utc) + timedelta(minutes=CHALLENGE_MINUTES),
                ),
            )
        conn.commit()
        return token
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


def set_challenge_purpose(token: str, user_id: int, purpose: str) -> None:
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE driver_auth_challenges
                SET purpose = %s, expires_at = %s
                WHERE challenge_hash = %s
                  AND user_id = %s
                  AND expires_at > NOW()
                """,
                (
                    purpose,
                    datetime.now(timezone.utc) + timedelta(minutes=CHALLENGE_MINUTES),
                    _hash(token),
                    user_id,
                ),
            )
            if cur.rowcount != 1:
                raise HTTPException(status_code=401, detail="Login challenge expired")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


def require_challenge(token: str, purposes: set[str]) -> tuple[int, str, str | None]:
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, purpose, pending_phone
                FROM driver_auth_challenges
                WHERE challenge_hash = %s
                  AND expires_at > NOW()
                  AND attempts < max_attempts
                LIMIT 1
                """,
                (_hash(token),),
            )
            row = cur.fetchone()
        if not row or row[1] not in purposes:
            raise HTTPException(status_code=401, detail="Login challenge expired")
        return row[0], row[1], row[2]
    finally:
        return_connection(conn)


def issue_phone_code(challenge_token: str, user_id: int, phone: str, purpose: str) -> str:
    normalized_phone = normalize_phone(phone)
    code = f"{secrets.randbelow(1_000_000):06d}"
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO driver_sms_rate_limits (
                    user_id, window_date, send_count, last_sent_at
                )
                VALUES (%s, CURRENT_DATE, 1, NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET window_date = CURRENT_DATE,
                    send_count = CASE
                        WHEN driver_sms_rate_limits.window_date < CURRENT_DATE THEN 1
                        ELSE driver_sms_rate_limits.send_count + 1
                    END,
                    last_sent_at = NOW()
                WHERE driver_sms_rate_limits.window_date < CURRENT_DATE
                   OR (
                       driver_sms_rate_limits.send_count < 10
                       AND (
                           driver_sms_rate_limits.last_sent_at IS NULL
                           OR driver_sms_rate_limits.last_sent_at
                               < NOW() - INTERVAL '30 seconds'
                       )
                   )
                RETURNING send_count
                """,
                (user_id,),
            )
            if not cur.fetchone():
                raise HTTPException(
                    status_code=429,
                    detail="Verification message limit reached; try again later",
                )
            cur.execute(
                """
                UPDATE driver_auth_challenges
                SET purpose = %s, otp_hash = %s, pending_phone = %s,
                    attempts = 0, send_count = send_count + 1,
                    last_sent_at = NOW(), expires_at = %s
                WHERE challenge_hash = %s
                  AND user_id = %s
                  AND send_count < 5
                  AND (last_sent_at IS NULL OR last_sent_at < NOW() - INTERVAL '30 seconds')
                """,
                (
                    purpose,
                    _otp_hash(challenge_token, code),
                    normalized_phone,
                    datetime.now(timezone.utc) + timedelta(minutes=OTP_MINUTES),
                    _hash(challenge_token),
                    user_id,
                ),
            )
            if cur.rowcount != 1:
                raise HTTPException(
                    status_code=429,
                    detail="Wait before requesting another verification code",
                )
        conn.commit()
        _send_sms(normalized_phone, code)
        return normalized_phone
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


def create_mfa_challenge(user_id: int, phone: str) -> tuple[str, str]:
    token = create_onboarding_challenge(user_id)
    normalized = issue_phone_code(token, user_id, phone, "mfa")
    return token, normalized


def verify_phone_code(challenge_token: str, code: str) -> tuple[int, str, str]:
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, purpose, otp_hash, pending_phone, attempts, max_attempts
                FROM driver_auth_challenges
                WHERE challenge_hash = %s AND expires_at > NOW()
                FOR UPDATE
                """,
                (_hash(challenge_token),),
            )
            row = cur.fetchone()
            if not row or row[1] not in {
                "activation",
                "phone_verify",
                "mfa",
            }:
                raise HTTPException(status_code=401, detail="Verification code expired")
            if row[4] >= row[5] or not hmac.compare_digest(
                row[2] or "", _otp_hash(challenge_token, code.strip())
            ):
                cur.execute(
                    """
                    UPDATE driver_auth_challenges
                    SET attempts = attempts + 1
                    WHERE challenge_hash = %s
                    """,
                    (_hash(challenge_token),),
                )
                conn.commit()
                raise HTTPException(status_code=401, detail="Invalid verification code")
            cur.execute(
                "DELETE FROM driver_auth_challenges WHERE challenge_hash = %s",
                (_hash(challenge_token),),
            )
        conn.commit()
        return row[0], row[1], row[3]
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


def mark_phone_verified(user_id: int, phone: str) -> None:
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO driver_auth_state (
                    user_id, must_change_password, mfa_phone, phone_verified_at
                )
                VALUES (%s, FALSE, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET mfa_phone = EXCLUDED.mfa_phone,
                    phone_verified_at = NOW(),
                    updated_at = NOW()
                """,
                (user_id, phone),
            )
            cur.execute(
                """
                UPDATE employees
                SET cell_phone = %s, updated_at = NOW()
                WHERE employee_id = (
                    SELECT employee_id FROM driver_user_links WHERE user_id = %s
                )
                """,
                (phone, user_id),
            )
            if cur.rowcount != 1:
                raise HTTPException(status_code=409, detail="Driver account is not linked")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)

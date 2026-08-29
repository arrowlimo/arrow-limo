import json
import logging
from datetime import datetime, timedelta

import bcrypt

from ...db import get_connection, return_connection
from ...settings import get_settings
from .onboarding import ensure_auth_tables

logger = logging.getLogger("modern_backend.auth.credentials")


def _parse_permissions(raw_permissions) -> dict:
    if not raw_permissions:
        return {}
    if isinstance(raw_permissions, dict):
        return raw_permissions
    try:
        return json.loads(raw_permissions)
    except (TypeError, json.JSONDecodeError):
        return {}


def _is_active_user(status) -> bool:
    return not status or str(status).lower() == "active"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash) -> bool:
    if not password_hash:
        return False
    hash_bytes = password_hash.encode("utf-8") if isinstance(password_hash, str) else password_hash
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hash_bytes)
    except (TypeError, ValueError):
        logger.warning("Rejected malformed password hash")
        return False


def _fetch_user(where_clause: str, value):
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    u.user_id, l.employee_id, u.username,
                    u.email, u.role, u.password_hash,
                    u.permissions, u.status,
                    COALESCE(s.must_change_password, FALSE),
                    s.mfa_phone,
                    s.phone_verified_at,
                    COALESCE(
                        NULLIF(TRIM(COALESCE(e.first_name, '') || ' ' || COALESCE(e.last_name, '')), ''),
                        u.username
                    ) AS display_name,
                    u.locked_until,
                    COALESCE(u.failed_login_attempts, 0)
                FROM users u
                LEFT JOIN driver_auth_state s ON s.user_id = u.user_id
                LEFT JOIN driver_user_links l ON l.user_id = u.user_id
                LEFT JOIN employees e ON e.employee_id = l.employee_id
                WHERE {where_clause}
                LIMIT 1
                """,
                (value,),
            )
            row = cur.fetchone()
        return row
    finally:
        return_connection(conn)


def _user_payload(row) -> dict:
    return {
        "account_id": row[0],
        "employee_id": row[1],
        "username": row[2],
        "email": row[3],
        "role": row[4] or "user",
        "permissions": _parse_permissions(row[6]),
        "must_change_password": bool(row[8]),
        "mfa_phone": row[9],
        "phone_verified": row[10] is not None,
        "name": row[11] or row[2],
    }


def verify_user_credentials(username: str, password: str) -> dict | None:
    row = _fetch_user("LOWER(u.username) = LOWER(%s)", username.strip())
    if not row or not _is_active_user(row[7]):
        return None
    if row[12] and row[12] > datetime.now():
        return None
    if not verify_password(password, row[5]):
        _record_login_result(row[0], succeeded=False, failed_attempts=row[13])
        return None
    _record_login_result(row[0], succeeded=True, failed_attempts=0)
    return _user_payload(row)


def _record_login_result(user_id: int, succeeded: bool, failed_attempts: int) -> None:
    settings = get_settings()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if succeeded:
                cur.execute(
                    """
                    UPDATE users
                    SET failed_login_attempts = 0, locked_until = NULL,
                        last_login = NOW(), updated_at = NOW()
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
            else:
                next_attempt = failed_attempts + 1
                locked_until = (
                    datetime.now() + timedelta(minutes=settings.login_lockout_minutes)
                    if next_attempt >= settings.max_login_attempts
                    else None
                )
                cur.execute(
                    """
                    UPDATE users
                    SET failed_login_attempts = %s, locked_until = %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                    """,
                    (next_attempt, locked_until, user_id),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


def get_user_by_id(user_id: int) -> dict | None:
    row = _fetch_user("u.user_id = %s", user_id)
    if not row or not _is_active_user(row[7]):
        return None
    return _user_payload(row)


def replace_password(user_id: int, new_password: str) -> None:
    conn = get_connection()
    try:
        ensure_auth_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET password_hash = %s, updated_at = NOW(),
                    session_version = COALESCE(session_version, 1) + 1
                WHERE user_id = %s
                """,
                (hash_password(new_password), user_id),
            )
            if cur.rowcount != 1:
                raise LookupError("User account not found")
            cur.execute(
                """
                UPDATE driver_auth_state
                SET must_change_password = FALSE, password_changed_at = NOW(),
                    updated_at = NOW()
                WHERE user_id = %s
                """,
                (user_id,),
            )
            cur.execute(
                """
                UPDATE web_sessions
                SET revoked_at = NOW()
                WHERE employee_id = (
                    SELECT employee_id FROM driver_user_links WHERE user_id = %s
                )
                  AND revoked_at IS NULL
                """,
                (user_id,),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)

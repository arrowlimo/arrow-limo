import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from threading import Lock

from ...db import get_connection, return_connection

SESSION_TIMEOUT = 30 * 60
_SESSION_TABLE_READY = False
_SESSION_TABLE_LOCK = Lock()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _ensure_session_table(conn) -> None:
    global _SESSION_TABLE_READY
    if _SESSION_TABLE_READY:
        return
    with _SESSION_TABLE_LOCK:
        if _SESSION_TABLE_READY:
            return
        with conn.cursor() as cur:
            cur.execute(
                """
            CREATE TABLE IF NOT EXISTS web_sessions (
                token_hash CHAR(64) PRIMARY KEY,
                employee_id INTEGER NULL,
                auth_user_id INTEGER NULL,
                name TEXT NOT NULL,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                permissions JSONB NOT NULL DEFAULT '{}'::jsonb,
                impersonator_user_id INTEGER NULL,
                impersonator_username TEXT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL,
                revoked_at TIMESTAMPTZ NULL
            )
            """
            )
            cur.execute("ALTER TABLE web_sessions ALTER COLUMN employee_id DROP NOT NULL")
            cur.execute(
                "ALTER TABLE web_sessions ADD COLUMN IF NOT EXISTS auth_user_id INTEGER NULL"
            )
            cur.execute(
                """
                ALTER TABLE web_sessions
                ADD COLUMN IF NOT EXISTS impersonator_user_id INTEGER NULL
                """
            )
            cur.execute(
                """
                ALTER TABLE web_sessions
                ADD COLUMN IF NOT EXISTS impersonator_username TEXT NULL
                """
            )
            cur.execute(
                """
            CREATE INDEX IF NOT EXISTS idx_web_sessions_expiry
            ON web_sessions (expires_at)
            WHERE revoked_at IS NULL
            """
            )
        conn.commit()
        _SESSION_TABLE_READY = True


def create_session(
    employee_id: int | None,
    employee_name: str,
    role: str = "user",
    permissions: dict | None = None,
    username: str | None = None,
    auth_user_id: int | None = None,
    impersonator_user_id: int | None = None,
    impersonator_username: str | None = None,
) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=SESSION_TIMEOUT)
    conn = get_connection()
    try:
        _ensure_session_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM web_sessions
                WHERE expires_at < NOW() OR revoked_at IS NOT NULL
                """
            )
            cur.execute(
                """
                INSERT INTO web_sessions (
                    token_hash, employee_id, auth_user_id, name, username, role,
                    permissions, impersonator_user_id, impersonator_username,
                    expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                """,
                (
                    _token_hash(token),
                    employee_id,
                    auth_user_id,
                    employee_name,
                    username or employee_name,
                    role,
                    json.dumps(permissions or {}),
                    impersonator_user_id,
                    impersonator_username,
                    expires_at,
                ),
            )
        conn.commit()
        return token
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


def get_session(token: str | None) -> dict | None:
    if not token:
        return None
    conn = get_connection()
    try:
        _ensure_session_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    employee_id, auth_user_id, name, username, role, permissions,
                    impersonator_user_id, impersonator_username, expires_at
                FROM web_sessions
                WHERE token_hash = %s
                  AND revoked_at IS NULL
                  AND expires_at > NOW()
                LIMIT 1
                """,
                (_token_hash(token),),
            )
            row = cur.fetchone()
            if not row:
                return None
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=SESSION_TIMEOUT)
            cur.execute(
                """
                UPDATE web_sessions
                SET expires_at = %s
                WHERE token_hash = %s
                """,
                (expires_at, _token_hash(token)),
            )
        conn.commit()
        permissions = row[5] if isinstance(row[5], dict) else json.loads(row[5] or "{}")
        return {
            "employee_id": row[0],
            "auth_user_id": row[1],
            "name": row[2],
            "username": row[3],
            "role": row[4],
            "permissions": permissions,
            "impersonator_user_id": row[6],
            "impersonator_username": row[7],
            "expires_at": expires_at,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


def create_impersonated_session(
    support_token: str | None,
    employee_id: int,
    employee_name: str,
    role: str,
    permissions: dict,
    username: str,
    auth_user_id: int,
    allowed_support_roles: set[str],
) -> tuple[str, dict] | None:
    if not support_token or not allowed_support_roles:
        return None
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=SESSION_TIMEOUT)
    conn = get_connection()
    try:
        _ensure_session_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE web_sessions
                SET revoked_at = NOW()
                WHERE token_hash = %s
                  AND revoked_at IS NULL
                  AND expires_at > NOW()
                  AND LOWER(TRIM(role)) = ANY(%s)
                  AND auth_user_id IS NOT NULL
                RETURNING
                    employee_id, auth_user_id, name, username, role, permissions,
                    impersonator_user_id, impersonator_username, expires_at
                """,
                (_token_hash(support_token), sorted(allowed_support_roles)),
            )
            support_row = cur.fetchone()
            if not support_row:
                conn.rollback()
                return None
            cur.execute(
                """
                INSERT INTO web_sessions (
                    token_hash, employee_id, auth_user_id, name, username, role,
                    permissions, impersonator_user_id, impersonator_username,
                    expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                """,
                (
                    _token_hash(token),
                    employee_id,
                    auth_user_id,
                    employee_name,
                    username,
                    role,
                    json.dumps(permissions),
                    support_row[1],
                    support_row[3],
                    expires_at,
                ),
            )
        conn.commit()
        support_permissions = (
            support_row[5]
            if isinstance(support_row[5], dict)
            else json.loads(support_row[5] or "{}")
        )
        return token, {
            "employee_id": support_row[0],
            "auth_user_id": support_row[1],
            "name": support_row[2],
            "username": support_row[3],
            "role": support_row[4],
            "permissions": support_permissions,
            "impersonator_user_id": support_row[6],
            "impersonator_username": support_row[7],
            "expires_at": support_row[8],
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


def revoke_session(token: str | None) -> None:
    if not token:
        return
    conn = get_connection()
    try:
        _ensure_session_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE web_sessions
                SET revoked_at = NOW()
                WHERE token_hash = %s
                """,
                (_token_hash(token),),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


def parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None

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
    employee_id: int,
    employee_name: str,
    role: str = "user",
    permissions: dict | None = None,
    username: str | None = None,
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
                    token_hash, employee_id, name, username, role,
                    permissions, expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    _token_hash(token),
                    employee_id,
                    employee_name,
                    username or employee_name,
                    role,
                    json.dumps(permissions or {}),
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
                SELECT employee_id, name, username, role, permissions, expires_at
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
        permissions = row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}")
        return {
            "employee_id": row[0],
            "name": row[1],
            "username": row[2],
            "role": row[3],
            "permissions": permissions,
            "expires_at": expires_at,
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

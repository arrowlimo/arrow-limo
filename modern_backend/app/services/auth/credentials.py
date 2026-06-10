import json

from ...db import get_connection


def _parse_permissions(raw_permissions) -> dict:
    if not raw_permissions:
        return {}
    try:
        return json.loads(raw_permissions) if isinstance(raw_permissions, str) else raw_permissions
    except Exception:
        return {}


def _is_active_user(status) -> bool:
    return not status or str(status).lower() == "active"


def _verify_password_hash(password: str, password_hash) -> bool:
    if not password_hash:
        return False
    try:
        import bcrypt

        hash_bytes = (
            password_hash.encode("utf-8") if isinstance(password_hash, str) else password_hash
        )
        return bcrypt.checkpw(password.encode("utf-8"), hash_bytes)
    except Exception as pwd_err:
        print(f"Password verification error: {pwd_err}")
        return False


def _fetch_user_row(username: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT user_id, username, email, role, password_hash, permissions,
        status
        FROM users
        WHERE username = %s
        LIMIT 1
    """,
        (username,),
    )
    return conn, cur, cur.fetchone()


def _user_payload(user_row) -> dict:
    user_id, uname, _email, role, _pwd_hash, permissions, _status = user_row
    return {
        "employee_id": user_id,
        "name": uname,
        "role": role or "user",
        "permissions": _parse_permissions(permissions),
    }


def verify_user_credentials(username: str, password: str) -> dict | None:
    """Verify user login credentials against users table."""
    conn = None
    cur = None
    try:
        conn, cur, user = _fetch_user_row(username)
        if not user:
            return None

        status = user[6]
        if not _is_active_user(status):
            return None

        pwd_hash = user[4]
        if not _verify_password_hash(password, pwd_hash):
            return None

        return _user_payload(user)
    except Exception as e:
        print(f"Auth error: {e}")
        return None
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

import os
from collections.abc import Iterator
from contextlib import contextmanager, suppress

import psycopg2

_LOGGED_DB_TARGET = False


def _log_db_target_once():
    global _LOGGED_DB_TARGET
    if _LOGGED_DB_TARGET:
        return
    _LOGGED_DB_TARGET = True
    target = os.environ.get("DB_TARGET", "neon")
    host = os.environ.get("DB_HOST", "localhost")
    name = os.environ.get("DB_NAME", "almsdata")
    user = os.environ.get("DB_USER", "postgres")
    sslmode = os.environ.get("DB_SSLMODE") or "none"
    print(
        f"[DB TARGET] target={target} host={host} db={name} user={user} sslmode={sslmode}",
        flush=True,
    )


def get_connection():
    _log_db_target_once()
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "almsdata"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    )


@contextmanager
def cursor() -> Iterator[psycopg2.extensions.cursor]:  # type: ignore[name-defined]
    conn = get_connection()
    cur: psycopg2.extensions.cursor | None = None  # type: ignore[name-defined]
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        with suppress(Exception):
            if cur is not None:
                cur.close()
        with suppress(Exception):
            conn.close()

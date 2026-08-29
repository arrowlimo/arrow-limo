import os
from collections.abc import Iterator
from contextlib import contextmanager, suppress

import psycopg2
from psycopg2 import pool
from psycopg2.pool import PoolError

_connection_pool = None


class DatabaseConfigurationError(RuntimeError):
    pass


def _validate_production_database_config() -> None:
    if os.environ.get("ENVIRONMENT", "production").strip().lower() != "production":
        return

    required = (
        "ALMS_DEFAULT_DB_TARGET",
        "DB_HOST",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
    )
    if any(not os.environ.get(key, "").strip() for key in required):
        raise DatabaseConfigurationError("Production database configuration is incomplete")

    if os.environ["ALMS_DEFAULT_DB_TARGET"].strip().lower() != "neon":
        raise DatabaseConfigurationError("Production database target must be Neon")

    host = os.environ["DB_HOST"].strip().lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise DatabaseConfigurationError("Production database cannot use a local host")

    sslmode = os.environ.get("DB_SSLMODE", "").strip().lower()
    if sslmode not in {"require", "verify-ca", "verify-full"}:
        raise DatabaseConfigurationError("Production database TLS is required")


def _get_pool():
    """Get or create the connection pool."""
    global _connection_pool
    if _connection_pool is None:
        _validate_production_database_config()
        ssl_kwargs = {}
        if os.environ.get("DB_SSLMODE"):
            ssl_kwargs["sslmode"] = os.environ["DB_SSLMODE"]
        if os.environ.get("DB_CHANNEL_BINDING"):
            ssl_kwargs["channel_binding"] = os.environ["DB_CHANNEL_BINDING"]
        _connection_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=20,
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "5432")),
            database=os.environ.get("DB_NAME", "almsdata"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", ""),
            **ssl_kwargs,
        )
    return _connection_pool


def get_connection():
    """Get a live pooled connection, retrying stale connections."""
    max_retries = 3
    last_error: psycopg2.Error | PoolError | None = None

    for attempt in range(max_retries):
        try:
            conn_pool = _get_pool()
            conn = conn_pool.getconn()
            try:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute("SET search_path TO public")
                conn.autocommit = False
                return conn
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                conn_pool.putconn(conn, close=True)
                if attempt < max_retries - 1:
                    continue
                raise
        except (psycopg2.Error, PoolError) as exc:
            last_error = exc
            if attempt < max_retries - 1:
                continue
            raise

    if last_error is not None:
        raise last_error
    raise psycopg2.OperationalError("Failed to get database connection after retries")


def return_connection(conn):
    """Return a connection to the pool, rolled back for safe reuse."""
    with suppress(Exception):
        conn.rollback()
    try:
        conn_pool = _get_pool()
        conn_pool.putconn(conn)
    except Exception:
        with suppress(Exception):
            conn.close()


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
        return_connection(conn)


def close_all_connections():
    """Close all connections in the pool."""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None

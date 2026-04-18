import os
from collections.abc import Iterator
from contextlib import contextmanager, suppress

import psycopg2
from psycopg2 import pool

_LOGGED_DB_TARGET = False
_connection_pool = None


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


def _get_pool():
    """Get or create the connection pool"""
    global _connection_pool
    if _connection_pool is None:
        _log_db_target_once()
        _ssl_kwargs = {}
        if os.environ.get("DB_SSLMODE"):
            _ssl_kwargs["sslmode"] = os.environ["DB_SSLMODE"]
        if os.environ.get("DB_CHANNEL_BINDING"):
            _ssl_kwargs["channel_binding"] = os.environ["DB_CHANNEL_BINDING"]
        _connection_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=20,
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "5432")),
            database=os.environ.get("DB_NAME", "almsdata"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", ""),
            **_ssl_kwargs,
        )
    return _connection_pool


def get_connection():
    """Get a connection from the pool with auto-reconnect on failure"""
    _log_db_target_once()
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            conn_pool = _get_pool()
            conn = conn_pool.getconn()
            
            # Test if connection is alive
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                # Set search_path for Neon compatibility
                with conn.cursor() as cur:
                    cur.execute("SET search_path TO public")
                conn.commit()
                return conn
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                # Connection is stale, return it and try again
                conn_pool.putconn(conn, close=True)
                if attempt < max_retries - 1:
                    continue
                raise
                
        except Exception as e:
            if attempt == max_retries - 1:
                # Last attempt failed, try direct connection
                try:
                    _ssl_kwargs2 = {}
                    if os.environ.get("DB_SSLMODE"):
                        _ssl_kwargs2["sslmode"] = os.environ["DB_SSLMODE"]
                    if os.environ.get("DB_CHANNEL_BINDING"):
                        _ssl_kwargs2["channel_binding"] = os.environ["DB_CHANNEL_BINDING"]
                    conn = psycopg2.connect(
                        host=os.environ.get("DB_HOST", "localhost"),
                        port=int(os.environ.get("DB_PORT", "5432")),
                        database=os.environ.get("DB_NAME", "almsdata"),
                        user=os.environ.get("DB_USER", "postgres"),
                        password=os.environ.get("DB_PASSWORD", ""),
                        **_ssl_kwargs2,
                    )
                    with conn.cursor() as cur:
                        cur.execute("SET search_path TO public")
                    conn.commit()
                    return conn
                except Exception:
                    raise e
            continue
    
    raise psycopg2.OperationalError("Failed to get database connection after retries")


def return_connection(conn):
    """Return a connection to the pool"""
    try:
        conn_pool = _get_pool()
        conn_pool.putconn(conn)
    except Exception:
        # If pool doesn't exist or connection can't be returned, just close it
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
    """Close all connections in the pool (call on shutdown)"""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None

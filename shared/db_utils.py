"""
Shared database utilities for centralized connection management.
"""

import os
import psycopg2
from contextlib import contextmanager
from typing import Optional

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REMOVED***')
}


def get_db_connection():
    """Get PostgreSQL database connection."""
    return psycopg2.connect(**DB_CONFIG)


@contextmanager
def db_cursor(commit=False):
    """Context manager for safe database cursor with automatic cleanup."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def execute_query(query, params=None, fetch_one=False):
    """Execute query with automatic error handling and connection cleanup."""
    with db_cursor() as cur:
        cur.execute(query, params or ())
        if fetch_one:
            return cur.fetchone()
        return cur.fetchall()


def execute_update(query, params=None):
    """Execute INSERT/UPDATE/DELETE with automatic commit."""
    with db_cursor(commit=True) as cur:
        cur.execute(query, params or ())
        return cur.rowcount

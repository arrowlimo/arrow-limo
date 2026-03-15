import os
from collections.abc import Iterator
from contextlib import suppress, contextmanager

import psycopg2


def get_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', '5432')),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
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

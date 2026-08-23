import os

import psycopg2


def connect_db():
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return psycopg2.connect(dsn)

    password = os.getenv("NEON_DB_PASSWORD")
    if not password:
        raise RuntimeError(
            "Missing NEON_DB_PASSWORD. Set DATABASE_URL or NEON_DB_PASSWORD before running."
        )

    return psycopg2.connect(
        host=os.getenv("NEON_DB_HOST", "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech"),
        port=int(os.getenv("NEON_DB_PORT", "5432")),
        dbname=os.getenv("NEON_DB_NAME", "neondb"),
        user=os.getenv("NEON_DB_USER", "neondb_owner"),
        password=password,
        sslmode=os.getenv("NEON_DB_SSLMODE", "require"),
        channel_binding=os.getenv("NEON_DB_CHANNEL_BINDING", "require"),
    )

#!/usr/bin/env python3
"""
Build driver alias map from charters.
- Creates driver_alias_map(driver_key TEXT PRIMARY KEY, canonical_name TEXT, sources TEXT[])
- For each charter row with driver and/or driver_name, adds aliases:
  normalize(driver) -> canonical(normalize(driver_name) if present else normalize(driver))
  normalize(driver_name) -> canonical(normalize(driver_name))
"""
import os
import psycopg2

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')


def connect_db():
    return psycopg2.connect(dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD)


def normalize(name: str | None) -> str:
    if not name:
        return ''
    s = ' '.join(name.lower().split())
    s = s.replace('driver', '').strip()
    if s.startswith('dr') and len(s) > 2:
        s = s[2:]
    return s


def main():
    conn = connect_db()
    inserted = updated = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS driver_alias_map (
                        driver_key TEXT PRIMARY KEY,
                        canonical_name TEXT NOT NULL,
                        sources TEXT[] DEFAULT '{}'::text[]
                    )
                    """
                )
                # pull pairs
                cur.execute(
                    """
                    SELECT DISTINCT driver, driver_name
                    FROM charters
                    WHERE (driver IS NOT NULL OR driver_name IS NOT NULL)
                      AND charter_date IS NOT NULL
                      AND cancelled = FALSE
                    """
                )
                rows = cur.fetchall()
                # prepare upserts
                for driver, driver_name in rows:
                    key_code = normalize(driver)
                    key_name = normalize(driver_name)
                    canonical = key_name or key_code
                    if not canonical:
                        continue
                    # alias for driver code
                    if key_code:
                        cur.execute(
                            """
                            INSERT INTO driver_alias_map (driver_key, canonical_name, sources)
                            VALUES (%s, %s, ARRAY['charters'])
                            ON CONFLICT (driver_key) DO UPDATE SET
                                canonical_name = EXCLUDED.canonical_name,
                                sources = (driver_alias_map.sources || '{charters}')
                            """,
                            (key_code, canonical)
                        )
                        if cur.rowcount == 1:
                            inserted += 1
                        else:
                            updated += 1
                    # alias for driver name
                    if key_name:
                        cur.execute(
                            """
                            INSERT INTO driver_alias_map (driver_key, canonical_name, sources)
                            VALUES (%s, %s, ARRAY['charters'])
                            ON CONFLICT (driver_key) DO UPDATE SET
                                canonical_name = EXCLUDED.canonical_name,
                                sources = (driver_alias_map.sources || '{charters}')
                            """,
                            (key_name, canonical)
                        )
                        if cur.rowcount == 1:
                            inserted += 1
                        else:
                            updated += 1
        print(f"driver_alias_map upserted: inserted={inserted}, updated={updated}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()

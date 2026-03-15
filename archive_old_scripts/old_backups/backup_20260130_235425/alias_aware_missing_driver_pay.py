#!/usr/bin/env python3
"""
Alias-aware charter vs driver pay matcher.
- Loads driver_alias_map to normalize names for both charters and staging pay.
- Reports matched vs missing counts and top drivers by missing.
"""
import os
import psycopg2
from datetime import timedelta
from collections import defaultdict, Counter

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')


def connect_db():
    return psycopg2.connect(dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD)


def normalize(s: str | None) -> str:
    if not s:
        return ''
    s2 = ' '.join(s.lower().split())
    s2 = s2.replace('driver', '').strip()
    if s2.startswith('dr') and len(s2) > 2:
        s2 = s2[2:]
    return s2


def load_alias_map(cur):
    cur.execute("SELECT driver_key, canonical_name FROM driver_alias_map")
    m = dict(cur.fetchall())
    def canon(s: str | None) -> str:
        key = normalize(s)
        return m.get(key, key)
    return canon


def main():
    conn = connect_db()
    try:
        with conn:
            with conn.cursor() as cur:
                canon = load_alias_map(cur)
                # Load charters
                cur.execute(
                    """
                    SELECT charter_date, driver_name, driver, charter_id
                    FROM charters
                    WHERE charter_date IS NOT NULL AND cancelled=FALSE AND (driver IS NOT NULL OR driver_name IS NOT NULL)
                    """
                )
                charters = cur.fetchall()
                # Load pay
                cur.execute(
                    """
                    SELECT txn_date, driver_name, amount
                    FROM staging_driver_pay
                    WHERE driver_name IS NOT NULL AND txn_date IS NOT NULL
                    """
                )
                pays = cur.fetchall()

                pay_by = defaultdict(list)
                for d, name, amt in pays:
                    pay_by[(canon(name), d)].append(float(amt) if amt is not None else 0.0)

                matched = 0
                missing = 0
                missing_by_driver = Counter()
                for dt, dname, dcode, cid in charters:
                    candidates = [canon(dname), canon(dcode)]
                    candidates = [c for c in candidates if c]
                    if not candidates:
                        continue
                    found = False
                    for c in candidates:
                        if (c, dt) in pay_by:
                            found = True
                            break
                        for off in range(-7, 8):
                            if off == 0:
                                continue
                            d2 = dt + timedelta(days=off)
                            if (c, d2) in pay_by:
                                found = True
                                break
                        if found:
                            break
                    if found:
                        matched += 1
                    else:
                        missing += 1
                        # count under canonical primary
                        if candidates:
                            missing_by_driver[candidates[0]] += 1

                print(f"Charters considered: {len(charters):,}")
                print(f"Matched: {matched:,}")
                print(f"Missing: {missing:,}")
                print("Top drivers by missing (up to 10):")
                for k, v in missing_by_driver.most_common(10):
                    print(f"  {k}: {v}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()

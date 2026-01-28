#!/usr/bin/env python3
"""
Generate driver alias suggestions based on co-occurrence:
- Find dates where:
  - Charters have driver X (normalized)
  - Staging pay has driver Y (normalized)
  - X != Y
- Suggest Y -> X mapping (charter driver is canonical)
- Output CSV for review and optional auto-apply

Usage:
  python scripts/generate_driver_alias_suggestions.py --output alias_suggestions.csv
  python scripts/generate_driver_alias_suggestions.py --output alias_suggestions.csv --auto-apply
"""
import os
import argparse
import csv
from collections import defaultdict
import psycopg2

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REMOVED***')


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default='driver_alias_suggestions.csv', help='Output CSV file')
    ap.add_argument('--auto-apply', action='store_true', help='Apply suggestions to driver_alias_map')
    args = ap.parse_args()

    conn = connect_db()
    try:
        with conn:
            with conn.cursor() as cur:
                # Get all charter driver per date
                cur.execute(
                    """
                    SELECT charter_date, driver_name, driver
                    FROM charters
                    WHERE charter_date IS NOT NULL AND cancelled = FALSE AND (driver IS NOT NULL OR driver_name IS NOT NULL)
                    """
                )
                charters = cur.fetchall()
                charter_drivers_by_date = defaultdict(set)
                for dt, dname, dcode in charters:
                    for d in (dname, dcode):
                        if d:
                            charter_drivers_by_date[dt].add(normalize(d))

                # Get all staging pay driver per date
                cur.execute(
                    """
                    SELECT txn_date, driver_name
                    FROM staging_driver_pay
                    WHERE txn_date IS NOT NULL AND driver_name IS NOT NULL
                    """
                )
                pays = cur.fetchall()
                pay_drivers_by_date = defaultdict(set)
                for dt, dname in pays:
                    pay_drivers_by_date[dt].add(normalize(dname))

                # Find co-occurring dates with non-matching drivers
                suggestions = []
                for dt in sorted(charter_drivers_by_date.keys()):
                    charter_drivers = charter_drivers_by_date[dt]
                    pay_drivers = pay_drivers_by_date.get(dt, set())
                    # Suggest pay_driver -> charter_driver for drivers present on same date but not matching
                    for pd in pay_drivers:
                        if pd not in charter_drivers:
                            # Pick first charter driver as canonical (could be improved with heuristics)
                            canonical = sorted(charter_drivers)[0] if charter_drivers else pd
                            suggestions.append({
                                'date': dt,
                                'pay_driver_key': pd,
                                'charter_driver_canonical': canonical,
                                'confidence': 'low',  # placeholder
                            })

                # Write CSV
                with open(args.output, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['date', 'pay_driver_key', 'charter_driver_canonical', 'confidence'])
                    writer.writeheader()
                    writer.writerows(suggestions)
                print(f"Wrote {len(suggestions)} suggestions to {args.output}")

                if args.auto_apply:
                    # Apply unique suggestions to driver_alias_map
                    unique_mappings = {}
                    for s in suggestions:
                        pk = s['pay_driver_key']
                        ck = s['charter_driver_canonical']
                        if pk not in unique_mappings:
                            unique_mappings[pk] = ck
                    for pk, ck in unique_mappings.items():
                        cur.execute(
                            """
                            INSERT INTO driver_alias_map (driver_key, canonical_name, sources)
                            VALUES (%s, %s, ARRAY['co-occurrence'])
                            ON CONFLICT (driver_key) DO UPDATE SET
                                canonical_name = EXCLUDED.canonical_name,
                                sources = (driver_alias_map.sources || '{co-occurrence}')
                            """,
                            (pk, ck)
                        )
                    conn.commit()
                    print(f"Applied {len(unique_mappings)} unique mappings to driver_alias_map")
    finally:
        conn.close()


if __name__ == '__main__':
    main()

import os
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor

"""Populate fleet_number with vehicle_number where fleet_number is NULL/empty."""

def get_conn():
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_NAME = os.environ.get("DB_NAME", "almsdata")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def parse_args():
    p = argparse.ArgumentParser(description="Sync fleet_number from vehicle_number where missing")
    p.add_argument("--dry-run", action="store_true", help="Preview changes")
    p.add_argument("--write", action="store_true", help="Apply updates")
    return p.parse_args()


def main():
    args = parse_args()
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT vehicle_id, vehicle_number, fleet_number
                FROM vehicles
                WHERE fleet_number IS NULL OR TRIM(fleet_number) = ''
                """
            )
            rows = cur.fetchall()
            print(f"Rows missing fleet_number: {len(rows)}")
            preview = rows[:10]
            for r in preview:
                print(f"- id={r['vehicle_id']} vehicle_number={r['vehicle_number']} current fleet_number={r['fleet_number']}")
            if len(rows) > 10:
                print(f"... {len(rows) - 10} more")

            if args.dry_run and not args.write:
                print("Dry-run only. No changes applied.")
                return

            cur.execute(
                """
                UPDATE vehicles
                SET fleet_number = vehicle_number
                WHERE fleet_number IS NULL OR TRIM(fleet_number) = ''
                """
            )
            updated = cur.rowcount
            conn.commit()
            print(f"Updated rows: {updated}")

if __name__ == "__main__":
    main()

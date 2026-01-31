#!/usr/bin/env python3
"""
Backup the entire employees table to JSON and CSV in reports/ with a timestamped filename.
"""
import os
import json
import csv
import datetime as dt
import psycopg2
import psycopg2.extras as extras

PG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

ROOT = os.path.dirname(os.path.dirname(__file__))
REPORTS = os.path.join(ROOT, "reports")
STAMP = dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def main():
    os.makedirs(REPORTS, exist_ok=True)
    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            cur.execute("SELECT * FROM employees ORDER BY employee_id")
            rows = cur.fetchall()
            cols = [d.name for d in cur.description]
            # JSON
            json_path = os.path.join(REPORTS, f"employees_backup_{STAMP}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump([dict(r) for r in rows], f, ensure_ascii=False, indent=2, default=str)
            # CSV
            csv_path = os.path.join(REPORTS, f"employees_backup_{STAMP}.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                for r in rows:
                    w.writerow([str(r[c]) if r[c] is not None else "" for c in cols])
    print("Backup complete:")
    print(f" JSON: {json_path}")
    print(f" CSV : {csv_path}")


if __name__ == "__main__":
    main()

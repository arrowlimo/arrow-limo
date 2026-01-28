#!/usr/bin/env python3
"""Export key accounting reference tables to CSV for dedup review.

Outputs:
- reports/chart_of_accounts_export.csv (ordered by account_code)
- reports/category_mappings_export.csv
- reports/category_to_account_map_export.csv
"""
import csv
import datetime
import os
import psycopg2
import psycopg2.extras as extras

PG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
DATE_SUFFIX = datetime.date.today().isoformat()

def export_table(cur, sql, path):
    cur.execute(sql)
    rows = cur.fetchall()
    if not rows:
        print(f"No rows for {path}")
        return
    cols = [desc[0] for desc in cur.description]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}")


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            # chart_of_accounts ordered by account_code (text sort)
            export_table(
                cur,
                "SELECT * FROM chart_of_accounts ORDER BY account_code",
                os.path.join(REPORT_DIR, f"chart_of_accounts_export_{DATE_SUFFIX}.csv"),
            )
            # category_mappings
            export_table(
                cur,
                "SELECT * FROM category_mappings ORDER BY 1",
                os.path.join(REPORT_DIR, f"category_mappings_export_{DATE_SUFFIX}.csv"),
            )
            # category_to_account_map
            export_table(
                cur,
                "SELECT * FROM category_to_account_map ORDER BY 1",
                os.path.join(REPORT_DIR, f"category_to_account_map_export_{DATE_SUFFIX}.csv"),
            )


if __name__ == "__main__":
    main()

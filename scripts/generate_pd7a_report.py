"""Generate PD7A-style monthly payroll remittance report.

Outputs one CSV per year in ./reports: pd7a_{year}.csv
Each row: year, month, gross, cpp, ei, tax, employees_with_pay, notes

Notes:
- Uses driver_payroll with payroll_class NULL/'WAGE'/'BACKFILL'.
- Read-only; no database changes.
"""

from __future__ import annotations

import argparse
import csv
import os
import psycopg2


def get_db_connection():
    host = os.getenv("DB_HOST", "localhost")
    name = os.getenv("DB_NAME", "almsdata")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "***REMOVED***")
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def ensure_reports_dir() -> str:
    outdir = os.path.join(os.getcwd(), "reports")
    os.makedirs(outdir, exist_ok=True)
    return outdir


def main():
    ap = argparse.ArgumentParser(description="Generate PD7A-style monthly remittance report")
    ap.add_argument("--year", type=int, required=True)
    args = ap.parse_args()

    conn = get_db_connection(); cur = conn.cursor()
    cur.execute(
        """
        SELECT month,
               COALESCE(SUM(gross_pay),0) AS gross,
               COALESCE(SUM(cpp),0) AS cpp,
               COALESCE(SUM(ei),0) AS ei,
               COALESCE(SUM(tax),0) AS tax,
               COUNT(DISTINCT CASE WHEN COALESCE(gross_pay,0)<>0 OR COALESCE(cpp,0)<>0 OR COALESCE(ei,0)<>0 OR COALESCE(tax,0)<>0 THEN employee_id END) AS employees
        FROM driver_payroll
        WHERE year=%s
          AND (payroll_class IS NULL OR payroll_class IN ('WAGE','BACKFILL'))
        GROUP BY month
        ORDER BY month
        """,
        (args.year,),
    )
    rows = cur.fetchall(); cur.close(); conn.close()

    outdir = ensure_reports_dir()
    path = os.path.join(outdir, f"pd7a_{args.year}.csv")
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["year", "month", "gross", "cpp", "ei", "tax", "employees_with_pay", "notes"])
        for m, gross, cpp, ei, tax, empcount in rows:
            w.writerow([args.year, int(m or 0), float(gross or 0), float(cpp or 0), float(ei or 0), float(tax or 0), int(empcount or 0), ""])
    print(f"Wrote: {path}")


if __name__ == "__main__":
    main()

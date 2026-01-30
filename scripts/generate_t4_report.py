"""Generate T4-style annual report per employee.

Outputs CSV: t4_{year}.csv with columns:
  employee_id, full_name, ytd_gross, ytd_cpp, ytd_ei, ytd_tax, box14, box16, box18, box22, diff_box14, diff_box16, diff_box18, diff_box22

Notes:
- Uses driver_payroll (WAGE/BACKFILL) for YTD actuals, and t4_box_* columns if present.
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
import psycopg2
import psycopg2.extras


def get_db_connection():
    host = os.getenv("DB_HOST", "localhost")
    name = os.getenv("DB_NAME", "almsdata")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "***REDACTED***")
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def ensure_reports_dir() -> str:
    outdir = os.path.join(os.getcwd(), "reports")
    os.makedirs(outdir, exist_ok=True)
    return outdir


def table_columns(conn, table: str):
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,))
    cols = {r[0] for r in cur.fetchall()}
    cur.close()
    return cols


def employee_names(conn):
    cur = conn.cursor()
    try:
        cur.execute("SELECT employee_id, full_name FROM employees")
        return {int(eid): name or "" for eid, name in cur.fetchall() if eid is not None}
    except Exception:
        return {}
    finally:
        cur.close()


def main():
    ap = argparse.ArgumentParser(description="Generate T4-style annual report per employee")
    ap.add_argument("--year", type=int, required=True)
    args = ap.parse_args()

    conn = get_db_connection(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cols = table_columns(conn, 'driver_payroll')
    names = employee_names(conn)

    cur.execute(
        """
        SELECT employee_id,
               COALESCE(SUM(gross_pay),0) AS ytd_gross,
               COALESCE(SUM(cpp),0) AS ytd_cpp,
               COALESCE(SUM(ei),0) AS ytd_ei,
               COALESCE(SUM(tax),0) AS ytd_tax
        FROM driver_payroll
        WHERE year=%s AND (payroll_class IS NULL OR payroll_class IN ('WAGE','BACKFILL'))
        GROUP BY employee_id
        """,
        (args.year,),
    )
    ytd = {int(r['employee_id']): (float(r['ytd_gross']), float(r['ytd_cpp']), float(r['ytd_ei']), float(r['ytd_tax'])) for r in cur.fetchall() if r['employee_id'] is not None}

    t4 = defaultdict(lambda: (0.0,0.0,0.0,0.0))
    if {'t4_box_14','t4_box_16','t4_box_18','t4_box_22'} & cols:
        cur.execute(
            """
            SELECT employee_id,
                   COALESCE(SUM(t4_box_14),0) AS b14,
                   COALESCE(SUM(t4_box_16),0) AS b16,
                   COALESCE(SUM(t4_box_18),0) AS b18,
                   COALESCE(SUM(t4_box_22),0) AS b22
            FROM driver_payroll
            WHERE year=%s
            GROUP BY employee_id
            """,
            (args.year,),
        )
        for r in cur.fetchall():
            if r['employee_id'] is None:
                continue
            t4[int(r['employee_id'])] = (float(r['b14'] or 0), float(r['b16'] or 0), float(r['b18'] or 0), float(r['b22'] or 0))

    cur.close(); conn.close()

    outdir = ensure_reports_dir()
    path = os.path.join(outdir, f"t4_{args.year}.csv")
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["employee_id","full_name","ytd_gross","ytd_cpp","ytd_ei","ytd_tax","box14","box16","box18","box22","diff_box14","diff_box16","diff_box18","diff_box22"])
        for eid in sorted(ytd.keys() | t4.keys()):
            name = names.get(eid, "")
            yg, yc, yei, yt = ytd.get(eid, (0.0,0.0,0.0,0.0))
            b14,b16,b18,b22 = t4.get(eid, (0.0,0.0,0.0,0.0))
            w.writerow([eid, name, f"{yg:.2f}", f"{yc:.2f}", f"{yei:.2f}", f"{yt:.2f}", f"{b14:.2f}", f"{b16:.2f}", f"{b18:.2f}", f"{b22:.2f}", f"{(yg-b14):.2f}", f"{(yc-b16):.2f}", f"{(yei-b18):.2f}", f"{(yt-b22):.2f}"])
    print(f"Wrote: {path}")


if __name__ == "__main__":
    main()

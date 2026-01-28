"""Generate monthly pay statements per employee with YTD vs T4 comparison.

Outputs two CSVs in ./reports by default:
  - pay_statements_{year}.csv: one row per employee per month (gross, cpp, ei, tax, net)
  - pay_statements_{year}_summary.csv: one row per employee with YTD totals and T4 boxes + diffs

Rules:
  - Only includes payroll_class NULL, 'WAGE', or 'BACKFILL'. Excludes 'ADJUSTMENT'.
  - Uses driver_payroll table; joins employees for names when available.
  - T4 boxes sourced from driver_payroll columns (t4_box_14,16,18,22) if present; sums across the year.

Usage:
  python -X utf8 scripts/generate_pay_statements_by_employee.py --year 2012
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from typing import Dict, Tuple

import psycopg2
import psycopg2.extras


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


def table_columns(conn, table: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    cols = {r[0] for r in cur.fetchall()}
    cur.close()
    return cols


def fetch_employee_names(conn) -> Dict[int, str]:
    cur = conn.cursor()
    try:
        cur.execute("SELECT employee_id, full_name FROM employees")
    except Exception:
        return {}
    mapping = {}
    for eid, name in cur.fetchall():
        if eid is None:
            continue
        mapping[int(eid)] = name or ""
    cur.close()
    return mapping


def fetch_monthly_aggregates(conn, year: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT employee_id, month,
               COALESCE(SUM(gross_pay),0) AS gross,
               COALESCE(SUM(cpp),0) AS cpp,
               COALESCE(SUM(ei),0) AS ei,
               COALESCE(SUM(tax),0) AS tax,
               COALESCE(SUM(net_pay),0) AS net
        FROM driver_payroll
        WHERE year=%s
          AND (payroll_class IS NULL OR payroll_class IN ('WAGE','BACKFILL'))
        GROUP BY employee_id, month
        ORDER BY employee_id, month
        """,
        (year,),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


def fetch_t4_sums(conn, year: int, cols_available) -> Dict[int, Tuple[float, float, float, float]]:
    t4_cols = [c for c in ("t4_box_14", "t4_box_16", "t4_box_18", "t4_box_22") if c in cols_available]
    if not t4_cols:
        return {}
    # Build SELECT with COALESCE
    select_cols = ", ".join([f"COALESCE(SUM({c}),0) AS {c}" for c in t4_cols])
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        f"""
        SELECT employee_id, {select_cols}
        FROM driver_payroll
        WHERE year=%s
        GROUP BY employee_id
        """,
        (year,),
    )
    out: Dict[int, Tuple[float, float, float, float]] = {}
    for r in cur.fetchall():
        eid = r["employee_id"]
        if eid is None:
            continue
        # Map missing cols to 0
        b14 = float(r.get("t4_box_14", 0) or 0)
        b16 = float(r.get("t4_box_16", 0) or 0)
        b18 = float(r.get("t4_box_18", 0) or 0)
        b22 = float(r.get("t4_box_22", 0) or 0)
        out[int(eid)] = (b14, b16, b18, b22)
    cur.close()
    return out


def main():
    ap = argparse.ArgumentParser(description="Generate monthly pay statements per employee with YTD vs T4 comparison.")
    ap.add_argument("--year", type=int, required=True)
    args = ap.parse_args()

    conn = get_db_connection()
    outdir = ensure_reports_dir()
    try:
        cols = table_columns(conn, 'driver_payroll')
        name_map = fetch_employee_names(conn)
        rows = fetch_monthly_aggregates(conn, args.year)
        t4_map = fetch_t4_sums(conn, args.year, cols)

        # Structure monthly rows per employee
        monthly = defaultdict(dict)  # (eid) -> month -> dict
        employees_seen = set()
        for eid, month, gross, cpp, ei, tax, net in rows:
            if eid is None or month is None:
                continue
            eid = int(eid)
            m = int(month)
            monthly[eid][m] = {
                'gross': float(gross or 0),
                'cpp': float(cpp or 0),
                'ei': float(ei or 0),
                'tax': float(tax or 0),
                'net': float(net or 0),
            }
            employees_seen.add(eid)

        # Write detailed statements (one row per employee per month)
        detail_path = os.path.join(outdir, f"pay_statements_{args.year}.csv")
        with open(detail_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["employee_id", "full_name", "month", "gross", "cpp", "ei", "tax", "net"])
            for eid in sorted(employees_seen):
                full_name = name_map.get(eid, "")
                for m in range(1, 13):
                    vals = monthly[eid].get(m, {'gross':0, 'cpp':0, 'ei':0, 'tax':0, 'net':0})
                    w.writerow([eid, full_name, m, vals['gross'], vals['cpp'], vals['ei'], vals['tax'], vals['net']])

        # Write summary with YTD and T4 comparisons
        summary_path = os.path.join(outdir, f"pay_statements_{args.year}_summary.csv")
        with open(summary_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow([
                "employee_id", "full_name",
                "ytd_gross", "ytd_cpp", "ytd_ei", "ytd_tax", "ytd_net",
                "t4_box_14", "t4_box_16", "t4_box_18", "t4_box_22",
                "diff_box14", "diff_box16", "diff_box18", "diff_box22"
            ])
            for eid in sorted(employees_seen):
                full_name = name_map.get(eid, "")
                ytd_gross = sum(monthly[eid].get(m, {}).get('gross', 0) for m in range(1, 13))
                ytd_cpp = sum(monthly[eid].get(m, {}).get('cpp', 0) for m in range(1, 13))
                ytd_ei = sum(monthly[eid].get(m, {}).get('ei', 0) for m in range(1, 13))
                ytd_tax = sum(monthly[eid].get(m, {}).get('tax', 0) for m in range(1, 13))
                ytd_net = sum(monthly[eid].get(m, {}).get('net', 0) for m in range(1, 13))

                b14, b16, b18, b22 = t4_map.get(eid, (0.0, 0.0, 0.0, 0.0))
                diff14 = round(ytd_gross - b14, 2)
                diff16 = round(ytd_cpp - b16, 2)
                diff18 = round(ytd_ei - b18, 2)
                diff22 = round(ytd_tax - b22, 2)

                w.writerow([eid, full_name, ytd_gross, ytd_cpp, ytd_ei, ytd_tax, ytd_net,
                            b14, b16, b18, b22, diff14, diff16, diff18, diff22])

        print(f"Wrote: {detail_path}")
        print(f"Wrote: {summary_path}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()

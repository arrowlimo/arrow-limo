"""Year-wide gratuity (tips) vs payroll wages report.

Produces two CSVs in ./reports:
  - gratuity_vs_payroll_{year}_summary.csv   (one row per month)
  - gratuity_vs_payroll_{year}_detail.csv    (one row per employee per month)

Logic mirrors the single-month script:
  - Gratuity from charters using driver_gratuity_amount or driver_gratuity; estimates from percent when amount is absent.
  - Payroll gross from driver_payroll (WAGE/BACKFILL only).
  - Employee names joined from employees if available.
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


def table_columns(conn, table: str) -> Dict[str, str]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    out = {r[0]: r[1] for r in cur.fetchall()}
    cur.close()
    return out


def employee_names(conn) -> Dict[int, str]:
    cur = conn.cursor()
    try:
        cur.execute("SELECT employee_id, full_name FROM employees")
    except Exception:
        return {}
    m = {}
    for eid, name in cur.fetchall():
        if eid is None:
            continue
        m[int(eid)] = name or ""
    cur.close()
    return m


def fetch_charter_gratuities(conn, year: int, month: int):
    cols = table_columns(conn, 'charters')
    sel = [
        "assigned_driver_id" if "assigned_driver_id" in cols else "NULL AS assigned_driver_id",
        "driver_name" if "driver_name" in cols else "NULL AS driver_name",
        "rate" if "rate" in cols else "NULL AS rate",
        "driver_gratuity_amount" if "driver_gratuity_amount" in cols else "NULL AS driver_gratuity_amount",
        "driver_gratuity" if "driver_gratuity" in cols else "NULL AS driver_gratuity",
        "driver_gratuity_percent" if "driver_gratuity_percent" in cols else "NULL AS driver_gratuity_percent",
        "charter_date" if "charter_date" in cols else "NULL AS charter_date",
    ]
    # Determine proper month end
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{last_day:02d}"

    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        f"""
        SELECT {', '.join(sel)}
        FROM charters
        WHERE DATE(charter_date) >= %s AND DATE(charter_date) <= %s
        """,
        (start_date, end_date),
    )
    rows = cur.fetchall()
    cur.close()

    per_key = defaultdict(lambda: {"actual": 0.0, "est": 0.0, "charters": 0, "name": None})
    for r in rows:
        eid = r.get("assigned_driver_id")
        name = r.get("driver_name")
        rate = r.get("rate") or 0.0
        g_amt = r.get("driver_gratuity_amount")
        g_raw = r.get("driver_gratuity")
        g_pct = r.get("driver_gratuity_percent")

        try:
            rate = float(rate) if rate is not None else 0.0
        except Exception:
            rate = 0.0
        try:
            g_amt_v = float(g_amt) if g_amt is not None else 0.0
        except Exception:
            g_amt_v = 0.0
        try:
            g_raw_v = float(g_raw) if g_raw is not None else 0.0
        except Exception:
            g_raw_v = 0.0
        try:
            g_pct_v = float(g_pct) if g_pct is not None else 0.0
        except Exception:
            g_pct_v = 0.0

        actual = g_amt_v if g_amt_v > 0 else g_raw_v if g_raw_v > 0 else 0.0
        est = 0.0
        if actual <= 0 and g_pct_v and rate > 0:
            pct = g_pct_v / 100.0 if g_pct_v > 1 else g_pct_v
            if 0 < pct <= 1.0:
                est = round(rate * pct, 2)

        key = eid if eid is not None else ("UNLINKED", name or "")
        per_key[key]["actual"] += actual
        per_key[key]["est"] += est
        if actual > 0 or est > 0:
            per_key[key]["charters"] += 1
        per_key[key]["name"] = name

    return per_key


def fetch_payroll_gross(conn, year: int, month: int) -> Dict[int, float]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT employee_id, COALESCE(SUM(gross_pay),0) AS gross
        FROM driver_payroll
        WHERE year=%s AND month=%s
          AND (payroll_class IS NULL OR payroll_class IN ('WAGE','BACKFILL'))
        GROUP BY employee_id
        """,
        (year, month),
    )
    result = {}
    for eid, gross in cur.fetchall():
        if eid is None:
            continue
        result[int(eid)] = float(gross or 0)
    cur.close()
    return result


def main():
    ap = argparse.ArgumentParser(description="Year-wide gratuity vs payroll report")
    ap.add_argument("--year", type=int, default=2012)
    args = ap.parse_args()

    conn = get_db_connection()
    outdir = ensure_reports_dir()
    names = employee_names(conn)

    # Prepare CSV writers
    summary_path = os.path.join(outdir, f"gratuity_vs_payroll_{args.year}_summary.csv")
    detail_path = os.path.join(outdir, f"gratuity_vs_payroll_{args.year}_detail.csv")
    with open(summary_path, 'w', newline='', encoding='utf-8') as fs, \
         open(detail_path, 'w', newline='', encoding='utf-8') as fd:
        ws = csv.writer(fs)
        wd = csv.writer(fd)
        ws.writerow(["month", "payroll_gross", "gratuity_actual", "gratuity_estimated", "unlinked_gratuity"])
        wd.writerow(["employee_id", "full_name", "month", "gratuity_actual", "gratuity_estimated", "charters_with_gratuity", "payroll_gross"])

        for month in range(1, 13):
            per_key = fetch_charter_gratuities(conn, args.year, month)
            payroll = fetch_payroll_gross(conn, args.year, month)

            total_payroll = sum(payroll.values())
            total_actual = 0.0
            total_est = 0.0
            unlinked_total = 0.0

            for key, v in per_key.items():
                if isinstance(key, tuple) and key and key[0] == "UNLINKED":
                    unlinked_total += v["actual"] + v["est"]
                    # write detail with employee_id blank
                    wd.writerow(["", "UNLINKED: " + (v.get("name") or ""), month, f"{v['actual']:.2f}", f"{v['est']:.2f}", v['charters'], "0.00"])
                else:
                    eid = int(key)
                    nm = names.get(eid, "")
                    pg = payroll.get(eid, 0.0)
                    wd.writerow([eid, nm, month, f"{v['actual']:.2f}", f"{v['est']:.2f}", v['charters'], f"{pg:.2f}"])
                total_actual += v["actual"]
                total_est += v["est"]

            ws.writerow([month, f"{total_payroll:.2f}", f"{total_actual:.2f}", f"{total_est:.2f}", f"{unlinked_total:.2f}"])

    conn.close()
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {detail_path}")


if __name__ == "__main__":
    main()

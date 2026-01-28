import os
import sys
import csv
from typing import List, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor


HEADER = [
    "Reserve Date",
    "Reserve Number",
    "Service Fee",
    "Wait / Travel Time",
    "Extra Stops",
    "Gratuity",
    "Fuel Surcharge",
    "Beverage Charge",
    "Other Char (+)",
    "Other Char (-)",
    "Extra Gratuity",
    "G.S.T.",
    "Total",
    "REDUCED Revenue",
    "ADJUSTED Serv. Fee",
    "GST Calculate to",
    "RECONCILE to Total",
    "Difference",
    "GST Taxable",
    "GST",
    "Total S/B",
    "Diff. - Total",
    "Diff. - GST",
]


def get_db_connection():
    host = os.environ.get("DB_HOST", "localhost")
    name = os.environ.get("DB_NAME", "almsdata")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "***REMOVED***")
    port = int(os.environ.get("DB_PORT", "5432"))
    return psycopg2.connect(host=host, dbname=name, user=user, password=password, port=port)


def zero_pad_reserve(rn: str) -> str:
    if not rn:
        return rn
    s = rn.strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def get_distinct_years(conn) -> List[int]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT DISTINCT EXTRACT(YEAR FROM charter_date)::int AS y
            FROM charters
            WHERE charter_date IS NOT NULL
            ORDER BY y
            """
        )
        return [row["y"] for row in cur.fetchall()]


def fetch_year_rows(conn, year: int):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT reserve_number, charter_date
            FROM charters
            WHERE charter_date >= make_date(%s, 1, 1)
              AND charter_date <  make_date(%s + 1, 1, 1)
            ORDER BY charter_date, reserve_number
            """,
            (year, year),
        )
        return cur.fetchall()


def write_csv(rows, out_path: str):
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for r in rows:
            rn = zero_pad_reserve(str(r.get("reserve_number") or ""))
            dt = r.get("charter_date")
            dt_str = dt.date().isoformat() if hasattr(dt, "date") else (str(dt) if dt else "")
            w.writerow([
                dt_str,
                rn,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0,
            ])


def load_csv_pairs(csv_path: str) -> List[Tuple[str, str]]:
    pairs = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rn = zero_pad_reserve((row.get("Reserve Number") or "").strip())
            rd = (row.get("Reserve Date") or "").strip()
            if rn:
                pairs.append((rn, rd))
    return pairs


def fetch_db_map(conn, reserve_numbers: List[str]):
    if not reserve_numbers:
        return {}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT reserve_number, charter_date
            FROM charters
            WHERE reserve_number = ANY(%s)
            """,
            (reserve_numbers,),
        )
        rows = cur.fetchall()
    out = {}
    for r in rows:
        dt = r["charter_date"]
        out[r["reserve_number"]] = dt.date().isoformat() if hasattr(dt, "date") else (str(dt) if dt else "")
    return out


def verify_csv_against_db(conn, csv_path: str) -> Tuple[int, int, int]:
    pairs = load_csv_pairs(csv_path)
    csv_map = {rn: rd for rn, rd in pairs}
    rlist = list(csv_map.keys())
    db_map = fetch_db_map(conn, rlist)
    missing = sum(1 for rn in rlist if rn not in db_map)
    mismatches = 0
    for rn in rlist:
        if rn in db_map:
            if csv_map[rn] and db_map[rn] and csv_map[rn] != db_map[rn]:
                mismatches += 1
    return len(rlist), missing, mismatches


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    conn = get_db_connection()
    try:
        years = get_distinct_years(conn)
        print(f"Years found in charters: {years}")
        results = []
        for y in years:
            out_name = f"recreated_{y}_charge_summary.csv"
            out_path = os.path.join(root, out_name)
            rows = fetch_year_rows(conn, y)
            write_csv(rows, out_path)
            total, missing, mismatches = verify_csv_against_db(conn, out_path)
            status = "PASS" if missing == 0 and mismatches == 0 else "WARN"
            print(f"{y}: {status} | CSV reserves: {total}, Missing: {missing}, Date mismatches: {mismatches}")
            results.append((y, status, total, missing, mismatches))
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # Summary
    print("\n=== OVERALL SUMMARY ===")
    passes = sum(1 for _, s, *_ in results if s == "PASS")
    warns = len(results) - passes
    print(f"PASS: {passes}, WARN: {warns}, Total years: {len(results)}")


if __name__ == "__main__":
    main()

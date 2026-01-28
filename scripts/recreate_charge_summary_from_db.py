import os
import sys
import csv
from datetime import date

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


def fetch_charters_for_year(conn, year: int):
    start = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT reserve_number, charter_date
            FROM charters
            WHERE charter_date >= %s AND charter_date < %s
            ORDER BY charter_date, reserve_number
            """,
            (start, end),
        )
        return cur.fetchall()


def write_recreated_csv(rows, out_path):
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for r in rows:
            rn = zero_pad_reserve(str(r.get("reserve_number") or ""))
            dt = r.get("charter_date")
            # Normalize to YYYY-MM-DD
            if hasattr(dt, "date"):
                dt_str = dt.date().isoformat()
            else:
                dt_str = str(dt) if dt else ""
            # Fill non-essential columns with 0.0 to match format expectations
            data = [
                dt_str,
                rn,
                0.0,  # Service Fee
                0.0,  # Wait / Travel Time
                0.0,  # Extra Stops
                0.0,  # Gratuity
                0.0,  # Fuel Surcharge
                0.0,  # Beverage Charge
                0.0,  # Other Char (+)
                0.0,  # Other Char (-)
                0.0,  # Extra Gratuity
                0.0,  # G.S.T.
                0.0,  # Total
                0.0,  # REDUCED Revenue
                0.0,  # ADJUSTED Serv. Fee
                0.0,  # GST Calculate to
                0.0,  # RECONCILE to Total
                0.0,  # Difference
                0.0,  # GST Taxable
                0.0,  # GST
                0.0,  # Total S/B
                0.0,  # Diff. - Total
                0.0,  # Diff. - GST
            ]
            w.writerow(data)


def main():
    if len(sys.argv) < 2:
        print("Usage: python recreate_charge_summary_from_db.py <year>")
        sys.exit(2)
    try:
        year = int(sys.argv[1])
    except ValueError:
        print("Year must be an integer like 2013")
        sys.exit(2)

    out_name = f"recreated_{year}_charge_summary.csv"
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, out_name))
    print(f"Recreating charge summary for {year} → {out_path}")

    conn = get_db_connection()
    try:
        rows = fetch_charters_for_year(conn, year)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print(f"Charters found: {len(rows)}")
    write_recreated_csv(rows, out_path)
    print("DONE")


if __name__ == "__main__":
    main()

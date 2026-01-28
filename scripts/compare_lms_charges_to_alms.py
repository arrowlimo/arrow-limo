#!/usr/bin/env python
"""
Compare LMS (Access) charter charges/billing to almsdata (PostgreSQL).
Focus: per-reserve charge totals and charter totals to find deltas that need syncing.
No data is modified.
"""
import json
import os
from decimal import Decimal
from collections import defaultdict

import pyodbc
import psycopg2

MDB_FILE = r"L:\limo\backups\lms.mdb"
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

OUTPUT_JSON = r"L:\limo\reports\lms_vs_alms_charges.json"


def connect_mdb():
    try:
        conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_FILE};"
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"Error connecting to MDB: {e}")
        return None


def connect_pg():
    try:
        return psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None


def fetch_lms_charge_totals():
    conn = connect_mdb()
    if not conn:
        return {}

    try:
        cur = conn.cursor()
        # Access uses TOP, not LIMIT; grouping by Reserve_No
        cur.execute("SELECT Reserve_No, SUM(Amount) AS total_amount, COUNT(*) AS charge_count FROM Charge GROUP BY Reserve_No")
        rows = cur.fetchall()
        data = {}
        for row in rows:
            reserve_no = str(row[0]).strip() if row[0] is not None else None
            if not reserve_no:
                continue
            total_amount = float(row[1]) if row[1] is not None else 0.0
            charge_count = int(row[2]) if row[2] is not None else 0
            data[reserve_no] = {
                "total_amount": total_amount,
                "charge_count": charge_count,
            }
        print(f"✓ LMS charges loaded: {len(data)} reserves")
        return data
    except Exception as e:
        print(f"Error fetching LMS charges: {e}")
        return {}
    finally:
        conn.close()


def fetch_lms_reserve_balances():
    conn = connect_mdb()
    if not conn:
        return {}

    try:
        cur = conn.cursor()
        # Reserve_No is the business key in LMS Reserve
        cur.execute("SELECT Reserve_No, Balance FROM Reserve WHERE Reserve_No IS NOT NULL")
        rows = cur.fetchall()
        data = {}
        for row in rows:
            reserve_no = str(row[0]).strip() if row[0] is not None else None
            if not reserve_no:
                continue
            balance = float(row[1]) if row[1] is not None else 0.0
            data[reserve_no] = balance
        print(f"✓ LMS reserve balances loaded: {len(data)} reserves")
        return data
    except Exception as e:
        print(f"Error fetching LMS reserve balances: {e}")
        return {}
    finally:
        conn.close()


def fetch_pg_charge_totals():
    conn = connect_pg()
    if not conn:
        return {}

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT reserve_number,
                   SUM(COALESCE(amount,0) + COALESCE(gst_amount,0)) AS total_amount,
                   COUNT(*) AS charge_count
            FROM charter_charges
            GROUP BY reserve_number
            """
        )
        rows = cur.fetchall()
        data = {}
        for row in rows:
            reserve_no = str(row[0]).strip() if row[0] is not None else None
            if not reserve_no:
                continue
            total_amount = float(row[1]) if row[1] is not None else 0.0
            charge_count = int(row[2]) if row[2] is not None else 0
            data[reserve_no] = {
                "total_amount": total_amount,
                "charge_count": charge_count,
            }
        print(f"✓ almsdata charges loaded: {len(data)} reserves")
        return data
    except Exception as e:
        print(f"Error fetching almsdata charges: {e}")
        return {}
    finally:
        conn.close()


def fetch_pg_charter_totals():
    conn = connect_pg()
    if not conn:
        return {}

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT reserve_number,
                   COALESCE(total_amount_due,0) AS total_amount_due,
                   COALESCE(balance,0) AS balance
            FROM charters
            WHERE reserve_number IS NOT NULL
            """
        )
        rows = cur.fetchall()
        data = {}
        for row in rows:
            reserve_no = str(row[0]).strip() if row[0] is not None else None
            if not reserve_no:
                continue
            total_due = float(row[1]) if row[1] is not None else 0.0
            balance = float(row[2]) if row[2] is not None else 0.0
            data[reserve_no] = {
                "total_amount_due": total_due,
                "balance": balance,
            }
        print(f"✓ almsdata charters loaded: {len(data)} reserves")
        return data
    except Exception as e:
        print(f"Error fetching almsdata charters: {e}")
        return {}
    finally:
        conn.close()


def build_differences(lms_charges, lms_balances, pg_charges, pg_charters):
    diffs = []

    all_reserves = set(lms_charges.keys()) | set(pg_charges.keys())

    for res in all_reserves:
        lms_charge = lms_charges.get(res)
        pg_charge = pg_charges.get(res)
        pg_charter = pg_charters.get(res)
        lms_balance = lms_balances.get(res)

        lms_total = lms_charge["total_amount"] if lms_charge else 0.0
        pg_total = pg_charge["total_amount"] if pg_charge else 0.0
        total_due = pg_charter["total_amount_due"] if pg_charter else None
        balance = pg_charter["balance"] if pg_charter else None

        delta = lms_total - pg_total

        if abs(delta) > 0.01 or (total_due is not None and abs(total_due - lms_total) > 0.01):
            diffs.append(
                {
                    "reserve_number": res,
                    "lms_charge_total": round(lms_total, 2),
                    "alms_charge_total": round(pg_total, 2),
                    "alms_charter_total_due": round(total_due, 2) if total_due is not None else None,
                    "alms_charter_balance": round(balance, 2) if balance is not None else None,
                    "lms_balance_field": round(lms_balance, 2) if lms_balance is not None else None,
                    "delta_charge_totals": round(delta, 2),
                }
            )

    # Sort by absolute delta descending
    diffs.sort(key=lambda d: abs(d.get("delta_charge_totals", 0)), reverse=True)
    return diffs


def main():
    print("\n=== Loading LMS data (charges/balances) ===")
    lms_charges = fetch_lms_charge_totals()
    lms_balances = fetch_lms_reserve_balances()

    print("\n=== Loading almsdata data (charges/charters) ===")
    pg_charges = fetch_pg_charge_totals()
    pg_charters = fetch_pg_charter_totals()

    print("\n=== Comparing charge and billing totals ===")
    diffs = build_differences(lms_charges, lms_balances, pg_charges, pg_charters)

    summary = {
        "counts": {
            "lms_charge_reserves": len(lms_charges),
            "alms_charge_reserves": len(pg_charges),
            "alms_charters": len(pg_charters),
            "differences": len(diffs),
        },
        "sample_top20": diffs[:20],
    }

    output = {
        "summary": summary,
        "differences": diffs,
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Comparison complete. Differences: {len(diffs)}")
    print(f"✓ Saved to {OUTPUT_JSON}")
    if diffs:
        print("\nTop 5 deltas (LMS minus almsdata charge totals):")
        for item in diffs[:5]:
            print(
                f"  {item['reserve_number']}: LMS {item['lms_charge_total']:.2f} vs "
                f"alms charges {item['alms_charge_total']:.2f}, "
                f"charter total_due {item['alms_charter_total_due']}, delta {item['delta_charge_totals']:.2f}"
            )


if __name__ == "__main__":
    main()

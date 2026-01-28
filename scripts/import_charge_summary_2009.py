#!/usr/bin/env python
"""
Import 2009 charge summary CSV into general_ledger to backfill missing 2009 GL data.

Source file: l:/limo/recreated_2009_charge_summary.csv

For each reservation row, insert credits to:
- 4000 Limousine Service Income: GST Taxable amount
- 4300 Gratuity Income: Gratuity + Extra Gratuity (if > 0)
- 2200 GST/HST Payable: GST amount

Provenance: source_file = 'CHARGES:2009_recreated_csv'

Note: This importer records revenue-side entries and GST liability consistent with available data.
"""
from __future__ import annotations

import pandas as pd
import psycopg2
from decimal import Decimal, InvalidOperation
from datetime import datetime

CSV_PATH = r"L:/limo/recreated_2009_charge_summary.csv"


def to_decimal(x) -> Decimal | None:
    if pd.isna(x):
        return None
    try:
        d = Decimal(str(x))
        return d.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def get_connection():
    return psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="***REMOVED***")


def already_inserted(cur, date, num, account, credit) -> bool:
    cur.execute(
        """
        SELECT 1 FROM general_ledger
        WHERE date = %s AND COALESCE(num,'') = COALESCE(%s,'')
          AND account = %s AND COALESCE(credit,0) = %s AND source_file = 'CHARGES:2009_recreated_csv'
        LIMIT 1
        """,
        (date, num, account, credit),
    )
    return cur.fetchone() is not None


def import_2009():
    df = pd.read_csv(CSV_PATH)
    # Normalize headers
    df.columns = [c.strip() for c in df.columns]

    # Ensure required columns exist
    required = ["Reserve Date", "Reserve Number", "GST Taxable"]
    for col in required:
        if col not in df.columns:
            raise RuntimeError(f"Missing required column: {col}")

    # Pick GST column
    gst_col = "GST" if "GST" in df.columns else ("G.S.T." if "G.S.T." in df.columns else None)
    if not gst_col:
        raise RuntimeError("Missing GST column (GST or G.S.T.)")

    gratuity_cols = [c for c in ["Gratuity", "Extra Gratuity"] if c in df.columns]

    # Filter 2009 rows only
    df["Reserve Date"] = pd.to_datetime(df["Reserve Date"], errors="coerce")
    df = df[df["Reserve Date"].notna()]
    df2009 = df[(df["Reserve Date"].dt.year == 2009)]

    print(f"Rows in 2009: {len(df2009):,}")
    if len(df2009) == 0:
        return 0

    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    skipped = 0

    for idx, row in df2009.iterrows():
        try:
            date = row["Reserve Date"].date()
            num = str(row["Reserve Number"]).strip() if pd.notna(row["Reserve Number"]) else None
            base = to_decimal(row.get("GST Taxable"))
            gst = to_decimal(row.get(gst_col))
            gratuity = Decimal("0.00")
            for gc in gratuity_cols:
                val = to_decimal(row.get(gc))
                if val:
                    gratuity += val

            # Insert revenue base
            if base and base > 0:
                if not already_inserted(cur, date, num, "4000 Limousine Service Income", base):
                    cur.execute(
                        """
                        INSERT INTO general_ledger (date, transaction_type, num, name, account, credit, source_file, imported_at)
                        VALUES (%s, %s, %s, %s, %s, %s, 'CHARGES:2009_recreated_csv', NOW())
                        """,
                        (date, "Charge Summary", num, "Charter Revenue", "4000 Limousine Service Income", base),
                    )
                    inserted += 1
                else:
                    skipped += 1

            # Insert gratuity
            if gratuity and gratuity > 0:
                if not already_inserted(cur, date, num, "4300 Gratuity Income", gratuity):
                    cur.execute(
                        """
                        INSERT INTO general_ledger (date, transaction_type, num, name, account, credit, source_file, imported_at)
                        VALUES (%s, %s, %s, %s, %s, %s, 'CHARGES:2009_recreated_csv', NOW())
                        """,
                        (date, "Charge Summary", num, "Gratuity", "4300 Gratuity Income", gratuity),
                    )
                    inserted += 1
                else:
                    skipped += 1

            # Insert GST liability
            if gst and gst > 0:
                if not already_inserted(cur, date, num, "2200 GST/HST Payable", gst):
                    cur.execute(
                        """
                        INSERT INTO general_ledger (date, transaction_type, num, name, account, credit, source_file, imported_at)
                        VALUES (%s, %s, %s, %s, %s, %s, 'CHARGES:2009_recreated_csv', NOW())
                        """,
                        (date, "Charge Summary", num, "GST on Sales", "2200 GST/HST Payable", gst),
                    )
                    inserted += 1
                else:
                    skipped += 1

        except Exception as e:
            print(f"  [WARN] Row {idx} error: {e}")
            skipped += 1

    conn.commit()
    conn.close()

    print(f"  [OK] Inserted rows: {inserted:,}")
    print(f"  ⏭️  Skipped rows: {skipped:,}")
    return inserted


def main():
    print("IMPORT 2009 CHARGE SUMMARY -> GENERAL LEDGER")
    print("=" * 80)
    total = import_2009()
    print("=" * 80)
    print(f"IMPORT COMPLETE: {total:,} entries added (credits across revenue, gratuity, GST)")


if __name__ == "__main__":
    main()

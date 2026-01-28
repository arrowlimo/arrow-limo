#!/usr/bin/env python
"""
Import remaining QuickBooks Excel exports:
- initial transaction details.xlsx
- initial tax agency detail report.xlsx

Behavior:
- Reads with header row at index 3 (fourth row) to skip QuickBooks report banners
- Filters rows with valid Date and Account, and only imports dates before 2012-01-01
- Inserts into almsdata.general_ledger with provenance via source_file
"""
from __future__ import annotations

import sys
from pathlib import Path
from decimal import Decimal, InvalidOperation

import pandas as pd
import psycopg2


BASE_DIR = Path("L:/limo/quickbooks/old quickbooks")


def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )


def _to_decimal(val) -> Decimal | None:
    if pd.isna(val):
        return None
    try:
        return Decimal(str(val)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _get_amount_columns(row: pd.Series) -> tuple[Decimal | None, Decimal | None]:
    """Return (debit, credit) tuple from common QB report columns.

    Priority:
    - If separate Debit/Credit columns exist, use them
    - Else if a single Amount exists: positive -> debit, negative -> credit
    - Else return (None, None)
    """
    debit = None
    credit = None

    if "Debit" in row.index or "Credit" in row.index:
        debit = _to_decimal(row.get("Debit"))
        credit = _to_decimal(row.get("Credit"))
        # Normalize negatives just in case
        if debit is not None and debit < 0:
            debit = -debit
        if credit is not None and credit < 0:
            credit = -credit
    else:
        amt = _to_decimal(row.get("Amount"))
        if amt is not None:
            if amt >= 0:
                debit = amt
            else:
                credit = -amt

    return debit, credit


def _common_row_fields(row: pd.Series):
    txn_type = str(row.get("Type")) if pd.notna(row.get("Type")) else None
    num = str(row.get("Num")) if pd.notna(row.get("Num")) else None
    name = str(row.get("Name")) if pd.notna(row.get("Name")) else None
    account = str(row.get("Account")) if pd.notna(row.get("Account")) else None
    return txn_type, num, name, account


def import_transaction_details(file_path: Path) -> int:
    print("\n" + "=" * 80)
    print(f"IMPORTING TRANSACTION DETAILS: {file_path.name}")
    print("=" * 80)

    df = pd.read_excel(file_path, header=3)
    print(f"Total rows: {len(df):,}")

    if "Date" not in df.columns:
        print("  [WARN] No Date column - skipping file")
        return 0

    df = df[df["Date"].notna()]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df[df["Date"].notna()]
    df = df[df["Date"] < "2012-01-01"]

    print(f"Rows in 2003-2011: {len(df):,}")
    if len(df) == 0:
        return 0
    print(f"Date range: {df['Date'].min().date()} to {df['Date'].max().date()}")

    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    for idx, row in df.iterrows():
        try:
            txn_date = row["Date"].date()
            txn_type, num, name, account = _common_row_fields(row)
            if not account:
                skipped += 1
                continue

            debit, credit = _get_amount_columns(row)
            if debit is None and credit is None:
                skipped += 1
                continue

            if debit is not None:
                cur.execute(
                    """
                    INSERT INTO general_ledger (
                        date, transaction_type, num, name, account, debit, source_file, imported_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    (txn_date, txn_type, num, name, account, debit, "QB:transaction_details"),
                )
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1

            if credit is not None:
                cur.execute(
                    """
                    INSERT INTO general_ledger (
                        date, transaction_type, num, name, account, credit, source_file, imported_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    (txn_date, txn_type, num, name, account, credit, "QB:transaction_details"),
                )
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1

        except Exception as e:
            print(f"  [WARN] Row {idx}: {e}")
            skipped += 1

    conn.commit()
    conn.close()

    print(f"  [OK] Inserted: {inserted:,}")
    print(f"  ⏭️  Skipped: {skipped:,}")
    return inserted


def import_tax_agency_details(file_path: Path) -> int:
    print("\n" + "=" * 80)
    print(f"IMPORTING TAX AGENCY DETAILS: {file_path.name}")
    print("=" * 80)

    df = pd.read_excel(file_path, header=3)
    print(f"Total rows: {len(df):,}")

    if "Date" not in df.columns:
        print("  [WARN] No Date column - skipping file")
        return 0

    df = df[df["Date"].notna()]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df[df["Date"].notna()]
    df = df[df["Date"] < "2012-01-01"]

    print(f"Rows in 2003-2011: {len(df):,}")
    if len(df) == 0:
        return 0
    print(f"Date range: {df['Date'].min().date()} to {df['Date'].max().date()}")

    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    for idx, row in df.iterrows():
        try:
            txn_date = row["Date"].date()
            txn_type, num, name, account = _common_row_fields(row)
            if not account:
                skipped += 1
                continue

            debit, credit = _get_amount_columns(row)
            if debit is None and credit is None:
                # Some tax reports may have Amount column; already covered above.
                skipped += 1
                continue

            if debit is not None:
                cur.execute(
                    """
                    INSERT INTO general_ledger (
                        date, transaction_type, num, name, account, debit, source_file, imported_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    (txn_date, txn_type, num, name, account, debit, "QB:tax_agency_details"),
                )
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1

            if credit is not None:
                cur.execute(
                    """
                    INSERT INTO general_ledger (
                        date, transaction_type, num, name, account, credit, source_file, imported_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    (txn_date, txn_type, num, name, account, credit, "QB:tax_agency_details"),
                )
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1

        except Exception as e:
            print(f"  [WARN] Row {idx}: {e}")
            skipped += 1

    conn.commit()
    conn.close()

    print(f"  [OK] Inserted: {inserted:,}")
    print(f"  ⏭️  Skipped: {skipped:,}")
    return inserted


def main():
    print("IMPORTING TRANSACTION DETAILS AND TAX AGENCY DETAILS (to 2011-12-31)")
    print("=" * 80)

    total = 0

    tx_file = BASE_DIR / "initial transaction details.xlsx"
    if tx_file.exists():
        total += import_transaction_details(tx_file)
    else:
        print(f"Missing file: {tx_file}")

    tax_file = BASE_DIR / "initial tax agency detail report.xlsx"
    if tax_file.exists():
        total += import_tax_agency_details(tax_file)
    else:
        print(f"Missing file: {tax_file}")

    print("\n" + "=" * 80)
    print(f"IMPORT COMPLETE: {total:,} rows inserted")
    print("=" * 80)


if __name__ == "__main__":
    sys.exit(main())

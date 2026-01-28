#!/usr/bin/env python
"""
Parse QuickBooks IIF file (TRNS/SPL/ENDTRNS) and import only 2009-01-01..2011-12-31 rows
into almsdata.general_ledger with source_file='QB:IIF'.

Supported columns (common in IIF):
- TRNS: TRNSTYPE, DATE, ACCNT, NAME, AMOUNT, DOCNUM, MEMO
- SPL:  TRNSTYPE, DATE, ACCNT, NAME, AMOUNT, DOCNUM, MEMO

Notes:
- IIF dates are often in M/D/YY or M/D/YYYY; we'll parse with pandas to_datetime.
- AMOUNT on TRNS is total; SPL lines break down per account. We'll import SPL lines
  as individual ledger rows with debit/credit based on sign.
- We'll skip transactions outside 2009-01-01..2011-12-31.
"""
from __future__ import annotations

from pathlib import Path
from decimal import Decimal, InvalidOperation
import csv
import sys

import psycopg2
import pandas as pd


IIF_PATH = Path("L:/limo/quickbooks/old quickbooks/limousine.IIF")


def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )


def to_decimal(val) -> Decimal | None:
    if val is None:
        return None
    try:
        return Decimal(str(val)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def parse_iif_rows(path: Path):
    """Yield dicts for each row with type (TRNS or SPL) and columns mapping.

    IIF uses tab-delimited format with header rows beginning with !TRNS and !SPL
    and data rows beginning with TRNS and SPL.
    """
    current_headers = None
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f, delimiter="\t")
        for fields in reader:
            if not fields:
                continue
            tag = fields[0].strip() if fields else ""
            if tag.startswith("!"):
                # Header row, e.g., !TRNS\tTRNSID\tTRNSTYPE\tDATE\tACCNT\tAMOUNT ...
                current_headers = fields
                continue
            if tag in {"TRNS", "SPL", "ENDTRNS"}:
                if tag == "ENDTRNS":
                    yield {"ROWTYPE": "ENDTRNS"}
                    continue
                if current_headers is None:
                    continue
                row = {k: v for k, v in zip(current_headers, fields)}
                row["ROWTYPE"] = tag
                yield row


def import_iif_2009_2011():
    if not IIF_PATH.exists():
        print(f"Missing IIF file: {IIF_PATH}")
        return 0

    print("=" * 80)
    print(f"IMPORTING IIF (2009-2011): {IIF_PATH.name}")
    print("=" * 80)

    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    batch_count = 0

    # Track context of current transaction for defaults
    current_type = None
    current_date = None
    current_docnum = None
    current_name = None

    for row in parse_iif_rows(IIF_PATH):
        try:
            if row.get("ROWTYPE") == "ENDTRNS":
                current_type = None
                current_date = None
                current_docnum = None
                current_name = None
                continue

            rtype = row.get("ROWTYPE")
            if rtype == "TRNS":
                current_type = row.get("TRNSTYPE") or row.get("TRNSTYPE\n")
                # DATE might be in column "DATE" or "DATE\n"
                raw_date = row.get("DATE") or row.get("DATE\n")
                try:
                    ts = pd.to_datetime(raw_date, errors="coerce")
                except Exception:
                    ts = None
                current_date = ts.date() if ts is not None and pd.notna(ts) else None
                current_docnum = row.get("DOCNUM") or row.get("DOCNUM\n")
                current_name = row.get("NAME") or row.get("NAME\n")
                # We don't insert TRNS itself; we wait for SPL lines
                continue

            if rtype == "SPL":
                # Use SPL row values or fall back to TRNS context
                raw_date = row.get("DATE") or row.get("DATE\n")
                ts = pd.to_datetime(raw_date, errors="coerce") if raw_date else None
                txn_date = (ts.date() if ts is not None and pd.notna(ts) else current_date)
                if txn_date is None:
                    skipped += 1
                    continue
                if not (pd.Timestamp(2009, 1, 1).date() <= txn_date <= pd.Timestamp(2011, 12, 31).date()):
                    # Skip outside target window
                    continue

                txn_type = row.get("TRNSTYPE") or current_type
                num = row.get("DOCNUM") or current_docnum
                name = row.get("NAME") or current_name
                account = row.get("ACCNT") or row.get("ACCNT\n")
                if not account:
                    skipped += 1
                    continue

                amt = to_decimal(row.get("AMOUNT"))
                if amt is None:
                    skipped += 1
                    continue

                # Positive amounts in SPL often represent debits, negatives credits (depends on report)
                if amt >= 0:
                    cur.execute(
                        """
                        INSERT INTO general_ledger (
                            date, transaction_type, num, name, account, debit, source_file, imported_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, 'QB:IIF', NOW())
                        ON CONFLICT DO NOTHING
                        """,
                        (txn_date, txn_type, num, name, account, amt),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO general_ledger (
                            date, transaction_type, num, name, account, credit, source_file, imported_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, 'QB:IIF', NOW())
                        ON CONFLICT DO NOTHING
                        """,
                        (txn_date, txn_type, num, name, account, -amt),
                    )

                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1

                batch_count += 1
                if batch_count % 1000 == 0:
                    conn.commit()

        except Exception as e:
            print(f"  [WARN] Error: {e}")
            skipped += 1

    conn.commit()
    conn.close()

    print(f"  [OK] Inserted: {inserted:,}")
    print(f"  ⏭️  Skipped: {skipped:,}")
    return inserted


def main():
    print("QB IIF IMPORTER (2009-2011)")
    print("=" * 80)
    total = import_iif_2009_2011()
    print("=" * 80)
    print(f"IMPORT COMPLETE: {total:,} rows added from IIF")
    print("=" * 80)


if __name__ == "__main__":
    sys.exit(main())

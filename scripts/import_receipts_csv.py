#!/usr/bin/env python3
"""
Import Receipts from CSV (idempotent, GST-included model)
--------------------------------------------------------
- Reads a CSV/Excel-exported receipts file and inserts into receipts table.
- Normalizes flexible column names (date, vendor, amount, gst, description, category, employee_id, vehicle_id).
- GST/HST treated as INCLUDED in gross by default; extracted via rate/(1+rate) unless explicit gst column is present.
- Idempotent via source_hash (sha256 on date|vendor|gross|description); duplicates skipped.
- Dry-run by default; use --write to apply. Supports --year filter for auditing.

Safety:
- No deletions; follows table protection guidance.
- Uses api.get_db_connection() to respect DB_* env vars.
"""
import argparse
import csv
import hashlib
import pathlib
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api import get_db_connection  # type: ignore

TAX_RATES = {
    'AB': 0.05,
}

NORMALIZE_MAP = {
    'date': ['receipt_date', 'date', 'txn_date', 'transaction_date', 'posted_date'],
    'vendor': ['vendor', 'vendor_name', 'payee', 'merchant', 'name'],
    'gross': ['gross_amount', 'amount', 'total', 'total_amount', 'debit', 'credit'],
    'gst': ['gst_amount', 'hst_amount', 'tax', 'tax_amount'],
    'description': ['description', 'memo', 'notes', 'detail'],
    'category': ['category', 'type', 'class'],
    'employee_id': ['employee_id', 'emp_id'],
    'vehicle_id': ['vehicle_id', 'unit', 'unit_number', 'plate'],
}


def normalize_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    cols = {c.lower().strip().replace(' ', '_').replace('-', '_') for c in df.columns}
    mapping: Dict[str, Optional[str]] = {}
    for std, variations in NORMALIZE_MAP.items():
        chosen = None
        for v in variations:
            if v in cols:
                chosen = v
                break
        mapping[std] = chosen
    return mapping


def parse_date(val: str) -> Optional[datetime]:
    if not val:
        return None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%d-%b-%Y', '%b %d, %Y'):
        try:
            return datetime.strptime(val.strip(), fmt)
        except Exception:
            continue
    # Pandas fallback
    try:
        return pd.to_datetime(val, errors='coerce').to_pydatetime()
    except Exception:
        return None


def extract_gst_included(gross: float, province: str = 'AB') -> float:
    rate = TAX_RATES.get(province, 0.05)
    return round(gross * rate / (1 + rate), 2)


def compute_source_hash(date_str: str, vendor: str, gross: float, description: str) -> str:
    s = f"{date_str}|{vendor}|{gross:.2f}|{description}"
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def ensure_receipts_columns(cur):
    # Add source_hash if not present
    cur.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='receipts' AND column_name='source_hash'
            ) THEN
                ALTER TABLE receipts ADD COLUMN source_hash TEXT UNIQUE;
            END IF;
        END $$;
        """
    )


def insert_receipt(cur, row, dry_run: bool) -> bool:
    if dry_run:
        return False
    cur.execute(
        """
        INSERT INTO receipts (receipt_date, vendor_name, gross_amount, gst_amount, net_amount, description, category, employee_id, vehicle_id, is_business_expense, created_at, source_hash)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,true, NOW(), %s)
        ON CONFLICT (source_hash) DO NOTHING
        """,
        (
            row['date'], row['vendor'], row['gross'], row['gst'], row['net'], row['description'], row['category'], row['employee_id'], row['vehicle_id'], row['source_hash']
        )
    )
    return cur.rowcount > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', help='Path to CSV/XLSX receipts file')
    ap.add_argument('--sheet', help='Sheet name (for Excel)')
    ap.add_argument('--province', default='AB', help='Province for GST/HST rate (default AB)')
    ap.add_argument('--year', type=int, help='Only import rows in this year (by receipt date)')
    ap.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    args = ap.parse_args()

    path = pathlib.Path(args.file)
    if not path.exists():
        print(f"[FAIL] File not found: {path}")
        sys.exit(1)

    # Load data via pandas to handle Excel/CSV
    if path.suffix.lower() in ('.xlsx', '.xls'):
        df = pd.read_excel(path, sheet_name=args.sheet)
    else:
        df = pd.read_csv(path)

    # Normalize column names
    df.columns = [c.lower().strip().replace(' ', '_').replace('-', '_') for c in df.columns]
    mapping = normalize_columns(df)

    required = ['date', 'vendor', 'gross']
    if not all(mapping[k] for k in required):
        print(f"[FAIL] Missing required columns. Found mapping: {mapping}")
        sys.exit(1)

    conn = get_db_connection()
    cur = conn.cursor()

    ensure_receipts_columns(cur)

    inserted = 0
    skipped = 0
    processed = 0

    for _, rec in df.iterrows():
        date_val = str(rec.get(mapping['date']) or '').strip()
        dt = parse_date(date_val)
        if not dt:
            skipped += 1
            continue
        if args.year and dt.year != args.year:
            continue

        vendor = str(rec.get(mapping['vendor']) or '').strip()
        # Choose gross: prefer explicit gross_amount/amount; if both debit/credit present, pick non-zero net positive
        gross_raw = rec.get(mapping['gross'])
        try:
            gross = float(gross_raw)
        except Exception:
            try:
                gross = float(str(gross_raw).replace(',', '').replace('$', ''))
            except Exception:
                skipped += 1
                continue
        if gross < 0:
            gross = -gross  # normalize to positive for expense receipts

        desc = str(rec.get(mapping['description']) or '').strip()
        category = str(rec.get(mapping['category']) or '').strip() if mapping['category'] else None
        employee_id = int(rec.get(mapping['employee_id'])) if mapping['employee_id'] and pd.notna(rec.get(mapping['employee_id'])) else None
        vehicle_id = str(rec.get(mapping['vehicle_id']) or '').strip() if mapping['vehicle_id'] else None

        if mapping['gst'] and pd.notna(rec.get(mapping['gst'])):
            try:
                gst = float(rec.get(mapping['gst']))
            except Exception:
                gst = extract_gst_included(gross, args.province)
        else:
            gst = extract_gst_included(gross, args.province)
        net = round(gross - gst, 2)

        source_hash = compute_source_hash(dt.date().isoformat(), vendor, gross, desc)

        row = {
            'date': dt.date(),
            'vendor': vendor,
            'gross': round(gross, 2),
            'gst': round(gst, 2),
            'net': net,
            'description': desc,
            'category': category,
            'employee_id': employee_id,
            'vehicle_id': vehicle_id,
            'source_hash': source_hash,
        }

        inserted_now = insert_receipt(cur, row, dry_run=(not args.write))
        if inserted_now:
            inserted += 1
        else:
            skipped += 1
        processed += 1

    if args.write:
        conn.commit()
    else:
        conn.rollback()

    print("=== Import Receipts Summary ===")
    print(f"Processed: {processed}")
    print(f"Inserted:  {inserted}{'' if args.write else ' (dry-run)'}")
    print(f"Skipped:    {skipped}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()

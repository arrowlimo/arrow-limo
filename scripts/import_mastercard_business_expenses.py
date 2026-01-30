#!/usr/bin/env python3
"""
Import Mastercard business expenses from a CSV into the receipts table.

Safety:
- Dry-run by default. Use --apply to write.
- Idempotent via deterministic source_hash when the column exists.
- Defensive schema introspection to adapt to receipts schema variants.

Expected CSV columns (flexible, case-insensitive):
- date | transaction_date | posting_date
- amount | total | gross_amount (positive or negative)
- description | memo | details
- vendor | merchant | payee (optional; will fallback to description)

Tax model: Canadian GST/HST INCLUDED in gross amount (default province AB 5%).
"""
import os
import csv
import sys
import argparse
import hashlib
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import psycopg2


DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

TAX_RATES = {
    'AB': Decimal('0.05'), 'BC': Decimal('0.12'), 'SK': Decimal('0.11'),
    'MB': Decimal('0.12'), 'ON': Decimal('0.13'), 'QC': Decimal('0.14975'),
    'NB': Decimal('0.15'), 'NS': Decimal('0.15'), 'PE': Decimal('0.15'),
    'NL': Decimal('0.15'), 'YT': Decimal('0.05'), 'NT': Decimal('0.05'), 'NU': Decimal('0.05'),
}


def quantize_money(x: Decimal) -> Decimal:
    return x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_gst_included(gross: Decimal, province: str) -> tuple[Decimal, Decimal]:
    rate = TAX_RATES.get(province.upper(), Decimal('0.05'))
    if rate <= 0:
        return Decimal('0.00'), gross
    gst = (gross * rate) / (Decimal('1.0') + rate)
    gst = quantize_money(gst)
    net = quantize_money(gross - gst)
    return gst, net


def get_table_columns(cur, table_name: str) -> list[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,)
    )
    return [r[0] for r in cur.fetchall()]


def normalize_headers(hdrs: list[str]) -> dict:
    # Map normalized lowercase headers to actual names
    norm = {}
    for h in hdrs:
        key = h.strip().lower().replace('-', '_').replace(' ', '_')
        norm[key] = h
    return norm


def read_csv_rows(path: str) -> list[dict]:
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        hdr_map = normalize_headers(reader.fieldnames or [])
        rows = []
        for r in reader:
            rows.append({k: v for k, v in r.items()})
    return rows


def parse_amount(v: str) -> Decimal:
    if v is None:
        return Decimal('0')
    s = v.replace(',', '').replace('$', '').strip()
    if not s:
        return Decimal('0')
    try:
        return Decimal(s)
    except Exception:
        return Decimal('0')


def choose_first(row: dict, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in row and str(row[c]).strip():
            return row[c]
    # case-insensitive fallback
    for c in candidates:
        for k in row.keys():
            if k.lower() == c.lower() and str(row[k]).strip():
                return row[k]
    return None


def build_source_hash(date_str: str, vendor: str, amount: Decimal, description: str) -> str:
    basis = f"{date_str}|{vendor}|{amount}|{description}|MASTER_CARD"
    return hashlib.sha256(basis.encode('utf-8')).hexdigest()


def main():
    ap = argparse.ArgumentParser(description='Import Mastercard business expenses CSV into receipts (dry-run by default).')
    ap.add_argument('--csv', default=r'l:\\limo\\mastercard_business_expenses.csv', help='Path to CSV file')
    ap.add_argument('--province', default='AB', help='Province code for GST/HST')
    ap.add_argument('--category', default='credit_card', help='Receipts.category value to apply')
    ap.add_argument('--apply', action='store_true', help='Write changes to database')
    args = ap.parse_args()

    rows = read_csv_rows(args.csv)
    if not rows:
        print(f"[FAIL] No rows read from {args.csv}")
        return

    conn = psycopg2.connect(**DSN)
    cur = conn.cursor()
    receipt_cols = get_table_columns(cur, 'receipts')

    has_gross = 'gross_amount' in receipt_cols
    has_gst = 'gst_amount' in receipt_cols
    has_net = 'net_amount' in receipt_cols
    has_source_hash = 'source_hash' in receipt_cols
    has_source_ref = 'source_reference' in receipt_cols
    has_processing_notes = 'processing_notes' in receipt_cols

    planned = []
    skipped_existing = 0
    errors = 0

    for row in rows:
        # Pull fields
        date_raw = choose_first(row, ['date', 'transaction_date', 'posting_date']) or ''
        desc = choose_first(row, ['description', 'memo', 'details', 'narrative']) or ''
        vendor = choose_first(row, ['vendor', 'merchant', 'payee']) or desc or 'Unknown'
        amount_raw = choose_first(row, ['amount', 'total', 'gross_amount']) or '0'

        amt = parse_amount(amount_raw)
        # Some CSVs store purchases as negative numbers; normalize to positive expense
        gross = abs(amt)
        try:
            # Normalize date to YYYY-MM-DD
            # Try multiple formats
            dt = None
            for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d'):
                try:
                    dt = datetime.strptime(date_raw.strip(), fmt)
                    break
                except Exception:
                    continue
            if dt is None:
                # Last resort: keep raw
                date_str = date_raw.strip()
            else:
                date_str = dt.date().isoformat()
        except Exception:
            date_str = date_raw.strip()

        gst, net = calculate_gst_included(quantize_money(gross), args.province)
        s_hash = build_source_hash(date_str, vendor.strip(), quantize_money(gross), desc.strip())

        # Idempotency check
        if has_source_hash:
            cur.execute("SELECT 1 FROM receipts WHERE source_hash = %s LIMIT 1", (s_hash,))
            if cur.fetchone():
                skipped_existing += 1
                continue

        # Build insert dict using available columns
        rec = {}
        # Core
        if 'receipt_date' in receipt_cols:
            rec['receipt_date'] = date_str or None
        if 'vendor_name' in receipt_cols:
            rec['vendor_name'] = vendor[:200]
        if has_gross:
            rec['gross_amount'] = str(quantize_money(gross))
        elif 'amount' in receipt_cols:
            rec['amount'] = str(quantize_money(gross))
        if has_gst:
            rec['gst_amount'] = str(gst)
        if has_net:
            rec['net_amount'] = str(net)
        if 'description' in receipt_cols:
            rec['description'] = (desc or 'Mastercard expense').strip()[:500]
        if 'category' in receipt_cols:
            rec['category'] = args.category
        if 'is_business_expense' in receipt_cols:
            rec['is_business_expense'] = True
        if has_source_ref:
            rec['source_reference'] = 'Mastercard CSV Import'
        if has_source_hash:
            rec['source_hash'] = s_hash
        if has_processing_notes:
            rec['processing_notes'] = f"Imported from {os.path.basename(args.csv)}"

        planned.append(rec)

    # Summary
    print("\n=====================================================================")
    print("MASTERCARD CSV IMPORT - DRY RUN" if not args.apply else "MASTERCARD CSV IMPORT - APPLY")
    print("=====================================================================")
    print(f"CSV path: {args.csv}")
    print(f"Rows read: {len(rows)}")
    print(f"Planned inserts: {len(planned)}")
    print(f"Skipped existing (by source_hash): {skipped_existing}")

    if not planned:
        cur.close(); conn.close()
        print("Nothing to insert.")
        return

    # Show sample
    print("\nSample (up to 5):")
    for rec in planned[:5]:
        print({k: rec[k] for k in list(rec.keys())[:8]})

    if not args.apply:
        cur.close(); conn.close()
        print("\nDry run complete. Re-run with --apply to insert.")
        return

    # Apply inserts
    cols = list(planned[0].keys())
    placeholders = ",".join(["%s"] * len(cols))
    sql = f"INSERT INTO receipts ({','.join(cols)}) VALUES ({placeholders})"

    inserted = 0
    for rec in planned:
        try:
            values = [rec[c] for c in cols]
            cur.execute(sql, values)
            inserted += 1
        except Exception as e:
            # If idempotency is not supported by schema, we might hit duplicates; log and continue
            errors += 1
            print(f"  [WARN]  Insert failed for {rec.get('vendor_name','?')} on {rec.get('receipt_date','?')}: {e}")

    conn.commit()
    cur.close(); conn.close()

    print("\n=====================================================================")
    print("IMPORT RESULT")
    print("=====================================================================")
    print(f"Inserted: {inserted}")
    print(f"Errors: {errors}")


if __name__ == '__main__':
    main()

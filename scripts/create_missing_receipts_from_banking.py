"""
Create receipts for all unmatched banking debit transactions.

Rules
- Only create for debits (expenses); credits are handled via payments/revenue.
- Set `created_from_banking=true` and link `banking_transaction_id`.
- Compute GST/net using 5% GST included by default; set `business_personal='business'`.
- Duplicate prevention via `source_hash` and `WHERE NOT EXISTS`.
- Dry-run by default; require `--write` to commit.

Usage
  python -X utf8 l:\limo\scripts\create_missing_receipts_from_banking.py --year-start 2012 --year-end 2025 --dry-run
  python -X utf8 l:\limo\scripts\create_missing_receipts_from_banking.py --year-start 2012 --year-end 2025 --write --backup
"""
import argparse
import os
import psycopg2
import pandas as pd
from datetime import datetime
import hashlib

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def calculate_gst(gross_amount, tax_rate=0.05):
    gst_amount = gross_amount * tax_rate / (1 + tax_rate)
    net_amount = gross_amount - gst_amount
    return round(gst_amount, 2), round(net_amount, 2)

def fetch_unmatched_banking(conn, year_start, year_end):
    sql = """
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            bt.account_number,
            bt.vendor_extracted,
            bt.category,
            bt.source_file,
            bt.balance,
            bt.bank_id,
            bt.card_last4_detected,
            bt.is_transfer
                FROM banking_transactions bt
                WHERE bt.debit_amount > 0
                    AND EXTRACT(YEAR FROM bt.transaction_date) BETWEEN %s AND %s
                    AND NOT EXISTS (
                            SELECT 1 FROM receipts r WHERE r.banking_transaction_id = bt.transaction_id
                    )
                    AND NOT EXISTS (
                            SELECT 1 FROM banking_receipt_matching_ledger brl WHERE brl.banking_transaction_id = bt.transaction_id
                    )
    """
    return pd.read_sql_query(sql, conn, params=(year_start, year_end))

def compute_source_hash(bt_row):
    base = f"BT|{bt_row['transaction_id']}|{bt_row['transaction_date']}|{bt_row['debit_amount']}|{bt_row['vendor_extracted'] or bt_row['description'] or ''}|{bt_row['account_number']}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def build_receipt_values(bt_row):
    gross = float(bt_row['debit_amount'])
    gst, net = calculate_gst(gross)
    vals = {
        'receipt_date': bt_row['transaction_date'],
        'currency': 'CAD',
        'source_system': 'banking_auto',
        'source_reference': f"bt:{bt_row['transaction_id']}",
        'source_file': bt_row['source_file'],
        'validation_status': 'auto_created_unverified',
        'source_hash': compute_source_hash(bt_row),

        'vendor_name': bt_row['vendor_extracted'] or None,
        'canonical_vendor': None,
        'description': bt_row['description'],
        'gross_amount': gross,
        'gst_amount': gst,
        'net_amount': net,
        'expense_account': None,
        'payment_method': 'Bank',
        'canonical_pay_method': 'Bank',
        'card_type': None,
        'card_number': bt_row['card_last4_detected'] or None,
        'vehicle_id': None,
        'vehicle_number': None,
        'fuel_amount': None,
        'fuel': None,
        'category': bt_row['category'] or None,
        'classification': None,
        'sub_classification': None,
        'is_personal_purchase': False,
        'business_personal': 'business',
        'is_split_receipt': False,
        'parent_receipt_id': None,
        'is_driver_reimbursement': False,
        'reimbursed_via': None,
        'reimbursement_date': None,
        'cash_box_transaction_id': None,
        'comment': None,
        'deductible_status': None,
        'owner_personal_amount': 0,
        'amount_usd': None,
        'fx_rate': None,
        'gl_account_code': None,
        'gl_account_name': None,
        'gl_subcategory': None,
        'expense': net,
        'revenue': 0,
        'is_transfer': bt_row['is_transfer'],
        'mapped_bank_account_id': bt_row['bank_id'],
        'banking_transaction_id': bt_row['transaction_id'],
        'created_from_banking': True,
        'display_color': 'Green'
    }
    return vals

def apply_changes(conn, rows, write=False, backup=False):
    cur = conn.cursor()
    inserts = 0
    for vals in rows:
        # Ensure source_hash present
        src_hash = vals.get('source_hash')
        if not src_hash:
            src_hash = compute_source_hash(vals)
            vals['source_hash'] = src_hash
        cols = list(vals.keys())
        placeholders = ['%s'] * len(cols)
        values = list(vals.values())
        sql = (
            f"INSERT INTO receipts ({', '.join(cols)})\n"
            f"SELECT {', '.join(placeholders)}\n"
            "WHERE NOT EXISTS (\n"
            "  SELECT 1 FROM receipts r WHERE r.source_hash = %s\n"
            ")"
        )
        values.append(src_hash)
        if write:
            cur.execute(sql, values)
        inserts += 1
    if write:
        conn.commit()
    else:
        conn.rollback()
    cur.close()
    return inserts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--year-start', type=int, default=2012)
    ap.add_argument('--year-end', type=int, default=2025)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--backup', action='store_true')
    args = ap.parse_args()
    if not args.write:
        args.dry_run = True

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    print(f"Scanning unmatched banking debits {args.year_start}-{args.year_end}…")
    bt_df = fetch_unmatched_banking(conn, args.year_start, args.year_end)
    print(f"Found {len(bt_df):,} unmatched banking debits")

    rows = [build_receipt_values(r) for _, r in bt_df.iterrows()]
    count = apply_changes(conn, rows, write=args.write, backup=args.backup)
    if args.write:
        print(f"✅ Created {count} receipts (committed)")
    else:
        print(f"🔎 Dry-run: would create {count} receipts (rolled back)")

    conn.close()

if __name__ == '__main__':
    main()

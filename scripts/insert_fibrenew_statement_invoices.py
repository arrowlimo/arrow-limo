"""
Insert historical Fibrenew statement invoices (2017-11-29 to 2019-01-31)

- Parses L:\\limo\\receipts\\Document_20171129_0001.xlsx (2 sheets)
- Handles invoice prefixes: INV, 1NV (typo), NV (missing I)
- Inserts into receipts with source_system='FIBRENEW_STATEMENT'
- Skips any invoice numbers already inserted via 'FIBRENEW_INVOICE' (early 2019 loader)
- Idempotent via source_hash + pre-check on invoice number

Usage:
  python -X utf8 scripts/insert_fibrenew_statement_invoices.py          # dry-run
  python -X utf8 scripts/insert_fibrenew_statement_invoices.py --write  # apply
"""
import argparse
import hashlib
from decimal import Decimal
from datetime import datetime

import pandas as pd
import psycopg2
import re

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
EXCEL_FILE = r"L:\\limo\\receipts\\Document_20171129_0001.xlsx"

INVOICE_PREFIX_PATTERN = re.compile(r'(?:[1I]?NV)\s*#?\s*(\d+)', re.IGNORECASE)
ORIG_AMOUNT_PATTERN = re.compile(r'Orig\.\s*Amount\s*\$?([\d,]+\.?\d*)', re.IGNORECASE)


def parse_sheet(sheet_name: str):
    df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name, header=None)
    rows = []
    for idx, row in df.iterrows():
        # Date in first column
        val = row.iloc[0] if len(row) > 0 else None
        if pd.isna(val):
            continue
        dt = pd.to_datetime(val, errors='coerce')
        if pd.isna(dt):
            continue
        desc = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""
        m = INVOICE_PREFIX_PATTERN.search(desc)
        if not m:
            continue
        invoice_number = m.group(1)
        # Amount due is the first numeric after description
        amount_due = None
        balance = None
        for col_idx in range(2, min(len(row), 9)):
            v = row.iloc[col_idx]
            if pd.notna(v) and isinstance(v, (int, float)):
                if amount_due is None:
                    amount_due = Decimal(str(v))
                elif balance is None:
                    balance = Decimal(str(v))
                    break
        # Original amount from description (if present)
        om = ORIG_AMOUNT_PATTERN.search(desc)
        original_amount = Decimal(om.group(1).replace(',', '')) if om else None
        rows.append({
            'invoice_number': invoice_number,
            'invoice_date': dt.date(),
            'description': desc.strip(),
            'amount_due': amount_due,
            'original_amount': original_amount,
            'balance': balance,
        })
    return rows


def conn():
    return psycopg2.connect(**DB)


def categorize(amount: Decimal) -> str:
    # Heuristic: rent ~ 682.50, utilities are smaller
    try:
        if amount is not None and abs(amount - Decimal('682.50')) <= Decimal('2.00'):
            return '6800 - Rent'
    except Exception:
        pass
    return '6820 - Utilities'


def already_exists(cur, invoice_number: str) -> bool:
    # Skip if this invoice number already present from prior Fibrenew loader or statement
    cur.execute(
        """
        SELECT 1 FROM receipts
        WHERE source_reference IN (%s, %s)
           OR description ILIKE %s
        LIMIT 1
        """,
        (f"FIBRENEW-{invoice_number}", f"FIBRENEW-STATEMENT-{invoice_number}", f"%Invoice {invoice_number}%")
    )
    return cur.fetchone() is not None


def insert_statement_invoices(cur, apply=False):
    data = parse_sheet('Sheet1') + parse_sheet('Sheet2')
    # Deduplicate by invoice_number (if duplicated across sheets)
    by_inv = {}
    for d in data:
        by_inv[d['invoice_number']] = d
    invoices = list(by_inv.values())

    print("\n" + "="*110)
    print("FIBRENEW STATEMENT INVOICES (2017-11-29 to 2019-01-31)")
    print("="*110)
    print(f"{'Invoice':<10} {'Date':<12} {'Amount Due':>12} {'Orig Amt':>12} {'Category':<18} {'Action':<10}")
    print("-"*110)

    total_due = Decimal('0')
    total_insert = 0
    total_skip = 0

    # Sort by date then invoice number
    invoices.sort(key=lambda x: (x['invoice_date'], int(x['invoice_number'])))

    for inv in invoices:
        amt = inv['amount_due'] or Decimal('0')
        cat = categorize(amt)
        total_due += amt

        action = 'SKIP'
        if not already_exists(cur, inv['invoice_number']):
            action = 'INSERT' if apply else 'DRY-RUN'
            if apply:
                source_ref = f"FIBRENEW-STATEMENT-{inv['invoice_number']}"
                source_hash = hashlib.sha256(f"{source_ref}:{inv['invoice_date']}:{amt}".encode()).hexdigest()
                cur.execute(
                    """
                    INSERT INTO receipts (
                        source_system, source_reference, receipt_date, vendor_name, description,
                        gross_amount, gst_amount, expense_account, source_hash
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_hash) DO NOTHING
                    RETURNING id
                    """,
                    (
                        'FIBRENEW_STATEMENT',
                        source_ref,
                        inv['invoice_date'],
                        'Fibrenew Office Rent',
                        f"Invoice {inv['invoice_number']} (statement) - {inv['description']}",
                        amt,
                        Decimal('0.00'),  # unclear tax treatment on statement; preserve as base
                        cat,
                        source_hash,
                    )
                )
                r = cur.fetchone()
                if r:
                    total_insert += 1
                    action = f"INS#{r[0]}"
                else:
                    total_skip += 1
                    action = "DUP"
        else:
            total_skip += 1

        print(f"{inv['invoice_number']:<10} {str(inv['invoice_date']):<12} ${amt:>10,.2f} "
              f"${(inv['original_amount'] or Decimal('0')):>10,.2f} {cat:<18} {action:<10}")

    print("-"*110)
    print(f"{'TOTAL DUE':<22} ${total_due:>10,.2f}    Inserted: {total_insert}   Skipped: {total_skip}")
    print("="*110)

    return len(invoices), total_insert, total_skip, total_due


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply changes to database')
    args = ap.parse_args()

    cn = conn()
    try:
        cur = cn.cursor()
        count, ins, skip, total_due = insert_statement_invoices(cur, apply=args.write)
        if args.write:
            cn.commit()
            print(f"\n[OK] Inserted {ins} of {count} Fibrenew statement invoices. Skipped {skip}.")
        else:
            print(f"\nDry-run only. Found {count} invoices totaling ${total_due:,.2f}.")
            print("Re-run with --write to save.")
    finally:
        cn.close()

if __name__ == '__main__':
    main()

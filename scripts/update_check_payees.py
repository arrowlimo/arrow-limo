#!/usr/bin/env python3
"""
Update banking check payments with provided payee names.

- Uses a curated list of cheques (number, date, name, amount) from user attachment
- Matches `banking_transactions` by (date ± 3 days) AND debit_amount == amount
- Updates `vendor_extracted` and sets category to 'check_payment' when matched
- Idempotent: safe to re-run; includes --apply flag for changes

Notes:
- Verifies schema and adapts to `vendor_extracted` vs `vendor_name`
- Creates a `manual_check_payees` table to store the mapping and match status
"""

import argparse
from decimal import Decimal
from datetime import datetime, timedelta, date
from typing import List, Dict, Tuple, Optional
import psycopg2

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

# Provided cheques from attachment
CHEQUES: List[Dict] = [
    {"cheque_no":128, "date":"2013-01-26", "name":"Paul Mansell", "amount":"778.47"},
    {"cheque_no":129, "date":"2013-01-28", "name":"Fibrenew", "amount":"1268.48"},
    {"cheque_no":133, "date":"2013-02-03", "name":"With This Ring", "amount":"1050.00"},
    {"cheque_no":131, "date":"2013-02-01", "name":"City Of Red Deer", "amount":"435.00"},
    {"cheque_no":132, "date":"2013-02-01", "name":"City Of Red Deer", "amount":"125.00"},
    {"cheque_no":145, "date":"2013-02-05", "name":"Karen Richard", "amount":"400.00"},
    {"cheque_no":145, "date":"2013-02-08", "name":"Cal Red Consulting Ltd.", "amount":"1865.36"},
    {"cheque_no":147, "date":"2013-02-08", "name":"Cal Red Consulting Ltd.", "amount":"273.00"},
    {"cheque_no":130, "date":"2013-02-13", "name":"Ace Truck", "amount":"770.40"},
    {"cheque_no":136, "date":"2013-02-21", "name":"Michael Richard", "amount":"250.00"},
    {"cheque_no":144, "date":"2013-02-25", "name":"Michael Richard", "amount":"500.00"},
    {"cheque_no":142, "date":"2013-02-22", "name":"Earl's", "amount":"752.70"},
    {"cheque_no":152, "date":"2013-02-20", "name":"IFS Financial", "amount":"824.74"},
    {"cheque_no":143, "date":"2013-02-26", "name":"Karen Richard", "amount":"200.00"},
    {"cheque_no":152, "date":"2013-03-06", "name":"Paul Mansell", "amount":"1000.00"},
    {"cheque_no":160, "date":"2013-03-08", "name":"Jeannie Shillington", "amount":"200.00"},
    {"cheque_no":153, "date":"2013-03-10", "name":"Paul Mansell", "amount":"900.00"},
    {"cheque_no":159, "date":"2013-03-23", "name":"Jeannie Shillington", "amount":"300.00"},
    {"cheque_no":156, "date":"2013-03-26", "name":"Fibrenew", "amount":"100.00"},
    {"cheque_no":158, "date":"2013-04-02", "name":"Fibrenew", "amount":"1817.69"},
    {"cheque_no":160, "date":"2013-04-02", "name":"Fibrenew", "amount":"100.00"},
    {"cheque_no":161, "date":"2013-04-02", "name":"Red Deer Registries", "amount":"564.65"},
    {"cheque_no":162, "date":"2013-04-05", "name":"Paul Mansell", "amount":"200.00"},
    {"cheque_no":163, "date":"2013-04-04", "name":"Paul Mansell", "amount":"400.00"},
    {"cheque_no":164, "date":"2013-04-08", "name":"Jeannie Shillington", "amount":"1000.00"},
    {"cheque_no":60,  "date":"2012-09-26", "name":"Red Deer Registries", "amount":"908.15"},
]

# Simple employee vs vendor classification
EMPLOYEES = {"Paul Mansell", "Michael Richard", "Jeannie Shillington", "Karen Richard"}

DDL_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS manual_check_payees (
    id SERIAL PRIMARY KEY,
    cheque_no INTEGER,
    check_date DATE,
    payee_name VARCHAR(200),
    amount NUMERIC(12,2),
    matched_banking_id INTEGER,
    matched_on TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CHECK_COLS_SQL = """
SELECT column_name FROM information_schema.columns
WHERE table_name = 'banking_transactions' AND table_schema = 'public'
"""

FIND_CANDIDATE_SQL = """
SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
FROM banking_transactions
WHERE transaction_date BETWEEN %s AND %s
  AND COALESCE(debit_amount,0) = %s
ORDER BY transaction_date
"""

UPDATE_BT_SQL_VENDOR = """
UPDATE banking_transactions
SET vendor_extracted = %s,
    category = COALESCE(category, %s)
WHERE transaction_id = %s
"""

UPDATE_BT_SQL_VENDORNAME = """
UPDATE banking_transactions
SET vendor_name = %s,
    category = COALESCE(category, %s)
WHERE transaction_id = %s
"""

UPSERT_MAPPING_SQL = """
INSERT INTO manual_check_payees (cheque_no, check_date, payee_name, amount, matched_banking_id, matched_on, notes)
SELECT %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s
WHERE NOT EXISTS (
  SELECT 1 FROM manual_check_payees
  WHERE cheque_no = %s AND check_date = %s AND payee_name = %s AND amount = %s
);
"""

def get_conn():
    return psycopg2.connect(**DB)

def preview_and_update(dry_run: bool = True, day_window: int = 3) -> None:
    conn = get_conn()
    cur = conn.cursor()

    # Ensure mapping table exists
    cur.execute(DDL_CREATE_TABLE)

    # Discover banking_transactions columns
    cur.execute(CHECK_COLS_SQL)
    cols = {r[0] for r in cur.fetchall()}
    vendor_col = 'vendor_extracted' if 'vendor_extracted' in cols else ('vendor_name' if 'vendor_name' in cols else None)
    if not vendor_col:
        print("[WARN] Neither vendor_extracted nor vendor_name exists in banking_transactions. Aborting.")
        conn.rollback()
        cur.close(); conn.close()
        return

    print(f"Using vendor column: {vendor_col}")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}\n")

    total_matches = 0
    unmatched = []

    for chk in CHEQUES:
        cno = chk['cheque_no']
        cdate = datetime.strptime(chk['date'], "%Y-%m-%d").date()
        name = chk['name']
        amount = Decimal(chk['amount'])
        start = cdate - timedelta(days=day_window)
        end = cdate + timedelta(days=day_window)

        cur.execute(FIND_CANDIDATE_SQL, (start, end, amount))
        rows = cur.fetchall()

        payee_type = 'payroll' if name in EMPLOYEES else 'vendor'
        category_value = 'check_payment_' + payee_type

        if not rows:
            print(f"- Cheque #{cno} {cdate} ${amount}: No banking match")
            unmatched.append(chk)
            # Record mapping without banking id
            cur.execute(UPSERT_MAPPING_SQL, (cno, cdate, name, amount, None, 'no match', cno, cdate, name, amount))
            continue

        # Heuristic: prefer rows with description indicating cheque
        chosen = None
        for r in rows:
            desc = (r[2] or '').lower()
            if 'chq' in desc or 'cheq' in desc or 'check' in desc or 'cheque' in desc:
                chosen = r; break
        if not chosen:
            chosen = rows[0]

        tx_id, tx_date, desc, debit, credit = chosen
        total_matches += 1

        print(f"+ Cheque #{cno} {cdate} ${amount}: Matched tx {tx_id} on {tx_date} | desc='{desc}'")
        print(f"  → Set {vendor_col}='{name}', category='{category_value}'")

        if not dry_run:
            if vendor_col == 'vendor_extracted':
                cur.execute(UPDATE_BT_SQL_VENDOR, (name, category_value, tx_id))
            else:
                cur.execute(UPDATE_BT_SQL_VENDORNAME, (name, category_value, tx_id))

            cur.execute(UPSERT_MAPPING_SQL, (cno, cdate, name, amount, tx_id, 'matched', cno, cdate, name, amount))

    if not dry_run:
        conn.commit()
        print(f"\n✓ Applied updates. Matches: {total_matches}, Unmatched: {len(unmatched)}")
    else:
        conn.rollback()
        print(f"\nPreview complete. Matches: {total_matches}, Unmatched: {len(unmatched)} (no changes made)")

    cur.close(); conn.close()


def main():
    ap = argparse.ArgumentParser(description='Update check payees in banking_transactions')
    ap.add_argument('--apply', action='store_true', help='Apply updates (otherwise dry-run)')
    ap.add_argument('--days', type=int, default=3, help='Date window ±days for matching (default 3)')
    args = ap.parse_args()

    preview_and_update(dry_run=not args.apply, day_window=args.days)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Audit linkage/creation status between banking_transactions and receipts for
- NSF items
- Banking fees / service charges
- Withdrawals (cash)
- Deposits (cash or cheques)

Findings include:
- Overall banking→receipts linkage (via banking_transactions.receipt_id)
- Coverage by category (counts, linked vs unlinked)
- Suggestions for creation candidates (fees/NSF as expense receipts)

This script is read-only; it will not create any records.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


CATEGORY_PATTERNS = {
    # NSF related
    'nsf': [
        "nsf",
        "non sufficient",
        "insufficient funds",
        "returned item",
    ],
    # Bank fees / service charges
    'fees': [
        "fee",
        "fees",
        "service charge",
        "svc chg",
        "monthly fee",
        "account fee",
        "bank charge",
    ],
    # Cash withdrawals
    'withdrawal': [
        "withdrawal",
        "atm",
        "cash withdrawal",
    ],
    # Deposits (cash/cheques)
    'deposit': [
        "deposit",
        "cheque",
        "check",
        "ck ",
        "cash deposit",
        "branch deposit",
    ],
}


def build_amount_expr(cols):
    if 'debit_amount' in cols and 'credit_amount' in cols:
        return '(COALESCE(credit_amount,0) - COALESCE(debit_amount,0))'
    elif 'amount' in cols:
        return 'amount'
    return '0'


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Detect columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'banking_transactions'
    """)
    cols = {r['column_name'] for r in cur.fetchall()}
    amount_expr = build_amount_expr(cols)

    print('='*80)
    print('BANKING → RECEIPTS COVERAGE AUDIT')
    print('='*80)

    # Overall linkage
    cur.execute("SELECT COUNT(*) AS c FROM banking_transactions")
    total = cur.fetchone()['c']

    cur.execute("SELECT COUNT(*) AS c FROM banking_transactions WHERE receipt_id IS NOT NULL")
    linked_total = cur.fetchone()['c']

    print(f"Total banking rows:         {total}")
    print(f"Linked to receipts:         {linked_total}")
    print(f"Unlinked banking rows:      {total - linked_total}")

    # Helper to compute counts for a category
    def audit_category(name, patterns, sign_hint=None):
        like_clauses = " OR ".join(["LOWER(description) LIKE %s" for _ in patterns])
        params = [f"%{p.lower()}%" for p in patterns]
        sign_sql = ''
        if sign_hint == 'out':
            sign_sql = f" AND ({amount_expr}) < 0"
        elif sign_hint == 'in':
            sign_sql = f" AND ({amount_expr}) > 0"

        cur.execute(
            f"""
            SELECT COUNT(*) AS c,
                   SUM(CASE WHEN receipt_id IS NOT NULL THEN 1 ELSE 0 END) AS linked
            FROM banking_transactions
            WHERE ({like_clauses}){sign_sql}
            """,
            params
        )
        row = cur.fetchone()
        c = row['c'] or 0
        linked = row['linked'] or 0
        print(f"\n{name.upper()}:")
        print(f"  Candidates: {c}")
        print(f"  Linked:     {linked}")
        print(f"  Unlinked:   {c - linked}")

    # NSF and fees are typically outflows (debits)
    audit_category('nsf', CATEGORY_PATTERNS['nsf'], sign_hint='out')
    audit_category('fees', CATEGORY_PATTERNS['fees'], sign_hint='out')

    # Withdrawals (cash) also outflows
    audit_category('withdrawal', CATEGORY_PATTERNS['withdrawal'], sign_hint='out')

    # Deposits are inflows (credits)
    audit_category('deposit', CATEGORY_PATTERNS['deposit'], sign_hint='in')

    # For unlinked fees+nsf, propose creation candidates (sample 10)
    cur.execute(
        f"""
        SELECT transaction_id, transaction_date, description,
               {amount_expr} AS signed_amount
        FROM banking_transactions
        WHERE receipt_id IS NULL
          AND ((LOWER(description) LIKE %s) OR (LOWER(description) LIKE %s) OR (LOWER(description) LIKE %s) OR (LOWER(description) LIKE %s) OR (LOWER(description) LIKE %s) OR (LOWER(description) LIKE %s) OR (LOWER(description) LIKE %s))
          AND ({amount_expr}) < 0
        ORDER BY transaction_date DESC
        LIMIT 10
        """,
        [f"%{p.lower()}%" for p in CATEGORY_PATTERNS['fees']]
    )
    missing_samples = cur.fetchall()
    if missing_samples:
        print("\nSample missing fee/charge receipts (top 10):")
        for r in missing_samples:
            print(f"  {r['transaction_date']} | {r['transaction_id']} | {r['description']} | {r['signed_amount']}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()

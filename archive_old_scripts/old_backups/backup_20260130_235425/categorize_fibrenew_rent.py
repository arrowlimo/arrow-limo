"""
Categorize all Fibrenew payments as Office Rent.
- Updates banking_transactions.category where description mentions Fibrenew variants
- Updates receipts.category where vendor_name mentions Fibrenew variants

Dry-run by default; pass --write to apply.
"""
import argparse
import psycopg2

VARIANTS = [
    'fibrenew',
    'fibre new',
    'fib re new'
]

SQL_BT_PREVIEW = """
SELECT transaction_id, transaction_date, description, debit_amount, category
FROM banking_transactions
WHERE debit_amount IS NOT NULL
  AND (
    {like_clauses}
  )
ORDER BY transaction_date
LIMIT 50
"""

SQL_BT_UPDATE = """
UPDATE banking_transactions
SET category = 'Office Rent'
WHERE debit_amount IS NOT NULL
  AND (
    {like_clauses}
  )
"""

SQL_RCPT_PREVIEW = """
SELECT id, receipt_date, vendor_name, description, gross_amount, category
FROM receipts
WHERE vendor_name ILIKE ANY(ARRAY[{vendor_patterns}])
ORDER BY receipt_date DESC
LIMIT 50
"""

SQL_RCPT_UPDATE = """
UPDATE receipts
SET category = 'Office Rent'
WHERE vendor_name ILIKE ANY(ARRAY[{vendor_patterns}])
"""

def make_like_clauses(col: str, variants):
    parts = [f"LOWER({col}) LIKE %s" for _ in variants]
    return " OR ".join(parts), [f"%{v.lower()}%" for v in variants]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply updates')
    args = ap.parse_args()

    conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
    cur = conn.cursor()

    # Banking preview
    like_clause, params = make_like_clauses('description', VARIANTS)
    cur.execute(SQL_BT_PREVIEW.format(like_clauses=like_clause), params)
    bt_rows = cur.fetchall()
    print(f"\nBanking transactions mentioning Fibrenew (up to 50): {len(bt_rows)}")
    for r in bt_rows[:10]:
        print(f"  TX {r[0]} {r[1]} ${r[3] or 0:,.2f} | cat={r[4]} | {r[2]}")

    # Receipts preview
    vendor_patterns = ','.join(["%s"]*len(VARIANTS))
    cur.execute(SQL_RCPT_PREVIEW.format(vendor_patterns=vendor_patterns), [f"%{v}%" for v in VARIANTS])
    rcpt_rows = cur.fetchall()
    print(f"\nReceipts vendor matches (up to 50): {len(rcpt_rows)}")
    for r in rcpt_rows[:10]:
        print(f"  RCPT {r[0]} {r[1]} ${r[4]:,.2f} | cat={r[5]} | vendor={r[2]}")

    if args.write:
        # Update banking
        cur.execute(SQL_BT_UPDATE.format(like_clauses=like_clause), params)
        bt_updated = cur.rowcount
        # Update receipts
        cur.execute(SQL_RCPT_UPDATE.format(vendor_patterns=vendor_patterns), [f"%{v}%" for v in VARIANTS])
        rcpt_updated = cur.rowcount
        conn.commit()
        print(f"\nUpdated: banking_transactions={bt_updated}, receipts={rcpt_updated}")
    else:
        print("\nDry-run. Re-run with --write to apply category updates.")

    conn.close()

if __name__ == '__main__':
    main()

#!/usr/bin/env python
"""Report banking_transactions that are not linked to receipts/payments/charters.
Shows groups by category and source_file, and top sample rows.
"""
import psycopg2, os
from datetime import datetime

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD","***REMOVED***")

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*100)
print("UNLINKED BANKING TRANSACTIONS")
print("="*100)

cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE receipt_id IS NULL
      AND reconciled_receipt_id IS NULL
      AND reconciled_payment_id IS NULL
      AND reconciled_charter_id IS NULL
""")
total=cur.fetchone()[0]
print(f"Total unlinked banking transactions: {total}")

cur.execute("""
    SELECT category, source_file, COUNT(*) as cnt,
           ROUND(SUM(COALESCE(debit_amount,0)+COALESCE(credit_amount,0))::numeric,2) as total
    FROM banking_transactions
    WHERE receipt_id IS NULL
      AND reconciled_receipt_id IS NULL
      AND reconciled_payment_id IS NULL
      AND reconciled_charter_id IS NULL
    GROUP BY category, source_file
    ORDER BY cnt DESC
    LIMIT 15
""")
print("\nTop groups (category, source_file):")
for cat, sf, cnt, total_amt in cur.fetchall():
    print(f"  {cat or 'None':<25} {str(sf)[:30]:<30} {cnt:>5} | ${float(total_amt):>12.2f}")

cur.execute("""
    SELECT transaction_id, transaction_date, description,
           COALESCE(debit_amount,0) as d, COALESCE(credit_amount,0) as c, category, source_file
    FROM banking_transactions
    WHERE receipt_id IS NULL
      AND reconciled_receipt_id IS NULL
      AND reconciled_payment_id IS NULL
      AND reconciled_charter_id IS NULL
    ORDER BY transaction_date DESC
    LIMIT 20
""")
print("\nSample recent unlinked banking rows:")
for row in cur.fetchall():
    tid, tdate, desc, d, c, cat, sf = row
    print(f"  BT {tid}: {tdate} | d={d} c={c} | {cat or 'None'} | { (desc or '')[:70] } | {sf or 'None'}")

cur.close(); conn.close()

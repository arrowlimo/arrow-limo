#!/usr/bin/env python3
"""List all unmatched E-transfers with full descriptions for manual review."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Find all unmatched E-transfers (not matching payments)
query = '''
SELECT 
    bt.transaction_id,
    bt.transaction_date,
    bt.credit_amount,
    bt.description,
    bt.account_number
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
  AND NOT EXISTS (
    SELECT 1 FROM payments p 
    WHERE ABS(p.amount - bt.credit_amount) < 0.01
      AND p.payment_date::date >= bt.transaction_date::date - INTERVAL '7 days'
      AND p.payment_date::date <= bt.transaction_date::date + INTERVAL '7 days'
  )
ORDER BY bt.transaction_date DESC, bt.credit_amount DESC;
'''

cur.execute(query)
results = cur.fetchall()
cur.close()
conn.close()

print("\n" + "=" * 150)
print("ALL UNMATCHED E-TRANSFERS - FULL DESCRIPTIONS".center(150))
print("=" * 150)
print(f"\nTotal: {len(results)} E-transfers\n")

total = 0
for i, (tid, date, amount, desc, account) in enumerate(results, 1):
    total += amount
    print(f"{i:4d}. [{str(date)[:10]}] {amount:>10.2f}  {desc}")

print("\n" + "=" * 150)
print(f"TOTAL: {len(results)} E-transfers | ${total:,.2f}")
print("=" * 150)
print("\n⚠️  Please review and identify:")
print("   - Employee/driver payment names (Michael, Richard, Jerry, Schandrip, Jeannie, Shillington, etc.)")
print("   - Any other staff members\n")

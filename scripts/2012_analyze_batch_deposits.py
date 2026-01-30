"""
Analyze 2012 orphaned payments that don't match single charters.
These are likely batch deposits covering multiple charters.
"""
import os
import psycopg2
from datetime import date

DB = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '***REDACTED***'),
}

YEAR = 2012

s, e = date(YEAR, 1, 1), date(YEAR + 1, 1, 1)
conn = psycopg2.connect(**DB)
cur = conn.cursor()

# Get positive orphaned payments
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, notes
    FROM payments
    WHERE payment_date >= %s AND payment_date < %s
      AND reserve_number IS NULL
      AND amount > 0
    ORDER BY amount DESC
""", (s, e))

orphans = cur.fetchall()
print(f"=== Analyze 2012 Orphaned Payment Patterns ===")
print(f"Total orphaned: {len(orphans)}")
print(f"Total amount: ${sum(r[2] for r in orphans):,.2f}\n")

# Categorize by payment method
by_method = {}
for pid, pdate, amt, method, notes in orphans:
    method = method or 'Unknown'
    if method not in by_method:
        by_method[method] = {'count': 0, 'total': 0}
    by_method[method]['count'] += 1
    by_method[method]['total'] += float(amt)

print("By Payment Method:")
print(f"{'Method':<30} {'Count':>6} {'Total':>12}")
print('-' * 50)
for method in sorted(by_method.keys(), key=lambda m: by_method[m]['total'], reverse=True):
    data = by_method[method]
    print(f"{method:<30} {data['count']:>6} ${data['total']:>11,.2f}")

# Show top 20 by amount
print(f"\n\nTop 20 Largest Orphaned Payments:")
print(f"{'Date':<12} {'Amount':>12} {'Method':<15} {'Notes':<60}")
print('-' * 110)
for pid, pdate, amt, method, notes in orphans[:20]:
    notes_short = (notes or '')[:60]
    print(f"{pdate} ${float(amt):>11,.2f} {(method or 'Unknown'):<15} {notes_short}")

# Check if large payments are merchant deposits or batch deposits
print("\n\nBatch Deposit Pattern Detection:")
print("Looking for keywords: deposit, batch, merchant, settlement, QBO")
print('-' * 110)

batch_keywords = ['deposit', 'batch', 'merchant', 'settlement', 'qbo', 'square', 'visa', 'mcard', 'amex']
batch_count = 0
batch_total = 0

for pid, pdate, amt, method, notes in orphans:
    notes_lower = (notes or '').lower()
    if any(kw in notes_lower for kw in batch_keywords):
        batch_count += 1
        batch_total += float(amt)
        if batch_count <= 15:  # Show first 15
            print(f"{pdate} ${float(amt):>11,.2f} {(notes or '')[:80]}")

print(f"\nBatch deposit pattern matches: {batch_count} payments, ${batch_total:,.2f}")
print(f"Non-batch: {len(orphans) - batch_count} payments, ${sum(float(r[2]) for r in orphans) - batch_total:,.2f}")

cur.close()
conn.close()

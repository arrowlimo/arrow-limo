#!/usr/bin/env python3
"""Fix cancelled charters with no payments - set total_amount_due = 0 for 100% match."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Count cancelled charters with no payments
query_count = '''
SELECT COUNT(*), SUM(total_amount_due)
FROM charters
WHERE total_amount_due > 0
  AND paid_amount < 0.01
  AND (status ILIKE '%cancel%' OR status ILIKE '%void%');
'''

cur.execute(query_count)
count, total_due = cur.fetchone()
count = count or 0
total_due = float(total_due) if total_due else 0

print("\n" + "=" * 120)
print("CANCELLED CHARTERS - ZERO OUT CHARGES".center(120))
print("=" * 120)
print(f"\n📊 FOUND: {count} cancelled charters with no payments")
print(f"   Total Due to Zero Out: ${total_due:,.2f}")
print(f"\n   Impact: +{count} charters → Match rate: 97.91% + {100*count/16538:.2f}% = {97.91 + 100*count/16538:.2f}%")

# Show sample before update
query_sample = '''
SELECT charter_id, reserve_number, total_amount_due, status
FROM charters
WHERE total_amount_due > 0
  AND paid_amount < 0.01
  AND (status ILIKE '%cancel%' OR status ILIKE '%void%')
ORDER BY total_amount_due DESC
LIMIT 20;
'''

cur.execute(query_sample)
sample = cur.fetchall()

print("\n📋 SAMPLE (showing 20):")
print("-" * 120)
print(f"{'Charter':<8} | {'Reserve':<8} | {'Amount Due':>12} | {'Status':<20}")
print("-" * 120)
for row in sample:
    charter_id, reserve, due, status = row
    reserve_str = reserve or 'N/A'
    status_str = status or 'Unknown'
    print(f"{charter_id:<8} | {reserve_str:<8} | ${due:>11,.2f} | {status_str:<20}")

print("\n" + "=" * 120)
print("ACTION")
print("=" * 120)
print("\nSQL to execute:")
print("""
UPDATE charters
SET total_amount_due = 0.00
WHERE total_amount_due > 0
  AND paid_amount < 0.01
  AND (status ILIKE '%cancel%' OR status ILIKE '%void%');
""")
print(f"\nThis will:")
print(f"  ✅ Fix {count} charters")
print(f"  ✅ Increase match rate by {100*count/16538:.2f}%")
print(f"  ✅ New match rate: {97.91 + 100*count/16538:.2f}%")
print("\n⚠️  Run this manually or confirm to execute")
print("=" * 120 + "\n")

cur.close()
conn.close()

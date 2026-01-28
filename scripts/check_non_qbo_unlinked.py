#!/usr/bin/env python3
"""
Analyze non-QBO unlinked refunds (actual charter refunds that need linkage)
"""
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

conn = get_db_connection()
cur = conn.cursor()

print("Non-QBO Unlinked Refunds (likely actual charter refunds):")
print("="*100)

cur.execute("""
    SELECT COUNT(*), MIN(refund_date), MAX(refund_date), SUM(amount) 
    FROM charter_refunds 
    WHERE reserve_number IS NULL 
    AND (description NOT LIKE '%QBO Import%' OR description IS NULL)
""")
count, min_date, max_date, total_amt = cur.fetchone()
print(f"\nTotal: {count:,} refunds from {min_date} to {max_date}")
print(f"Amount: ${total_amt:,.2f}\n")

# Group by source
cur.execute("""
    SELECT source_file, COUNT(*), SUM(amount)
    FROM charter_refunds 
    WHERE reserve_number IS NULL 
    AND (description NOT LIKE '%QBO Import%' OR description IS NULL)
    GROUP BY source_file
    ORDER BY SUM(amount) DESC
""")
print("By source:")
for source, cnt, amt in cur.fetchall():
    print(f"  {source}: {cnt:,} refunds = ${amt:,.2f}")

# Top 30 unlinked
print("\n\nTop 30 unlinked non-QBO refunds:")
print("-"*100)
cur.execute("""
    SELECT id, refund_date, amount, customer, description, source_file
    FROM charter_refunds 
    WHERE reserve_number IS NULL 
    AND (description NOT LIKE '%QBO Import%' OR description IS NULL)
    ORDER BY amount DESC 
    LIMIT 30
""")

print(f"{'ID':>5} | {'Date':10} | {'Amount':>12} | {'Customer':25} | {'Description':40}")
print("-"*110)
for refund_id, date, amount, customer, desc, source in cur.fetchall():
    cust_str = (customer or "")[:25].ljust(25)
    desc_str = (desc or "")[:40]
    print(f"{refund_id:5} | {date} | ${amount:>10,.2f} | {cust_str} | {desc_str}")

cur.close()
conn.close()

#!/usr/bin/env python3
"""Calculate exact receipts to delete from verified banking."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("=== RECEIPTS FROM VERIFIED BANKING ===\n")

# Scotia verified receipts
cur.execute("""
    SELECT COUNT(DISTINCT r.receipt_id)
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.source_file = 'verified_2013_2014_scotia'
""")
scotia_receipts = cur.fetchone()[0]
print(f"Scotia verified receipts: {scotia_receipts:,}")

# CIBC 1615 verified receipts
cur.execute("""
    SELECT COUNT(DISTINCT r.receipt_id)
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.source_file = 'CIBC_7461615_2012_2017_VERIFIED.xlsx'
""")
cibc_receipts = cur.fetchone()[0]
print(f"CIBC 1615 verified receipts: {cibc_receipts:,}")

total_verified_receipts = scotia_receipts + cibc_receipts
print(f"\n{'='*60}")
print(f"Total verified receipts to DELETE: {total_verified_receipts:,}")

# Calculate remaining
cur.execute("SELECT COUNT(*) FROM receipts")
total_receipts = cur.fetchone()[0]
remaining = total_receipts - total_verified_receipts

print(f"Current total receipts: {total_receipts:,}")
print(f"After deletion: {remaining:,}")
print(f"Expected: 8,362")
print(f"Difference: {remaining - 8362:+,}")

# Year breakdown
print(f"\n{'='*60}")
print("=== BREAKDOWN BY YEAR ===\n")

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM bt.transaction_date) as year,
        bt.source_file,
        COUNT(DISTINCT r.receipt_id) as receipt_count
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.source_file IN ('verified_2013_2014_scotia', 'CIBC_7461615_2012_2017_VERIFIED.xlsx')
    GROUP BY year, bt.source_file
    ORDER BY year, bt.source_file
""")

print(f"{'Year':<8} {'Source':<40} {'Receipts':>12}")
print('-' * 65)
for row in cur.fetchall():
    year = int(row[0]) if row[0] else 0
    source = row[1][:38] if row[1] else "NULL"
    count = row[2]
    print(f"{year:<8} {source:<40} {count:>12,}")

cur.close()
conn.close()

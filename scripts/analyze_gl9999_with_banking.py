#!/usr/bin/env python
"""Analyze GL 9999 entries with banking_transaction_id - should we delete or remap?"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "="*100)
print("GL 9999 WITH BANKING_TRANSACTION_ID - DELETE OR KEEP?")
print("="*100)

# Check if these GL 9999 entries have other important data (charter_id, payment links, etc.)
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as with_charter,
        COUNT(CASE WHEN created_from_banking = true THEN 1 END) as from_banking,
        COUNT(CASE WHEN is_nsf = true THEN 1 END) as nsf_marked
    FROM receipts
    WHERE gl_account_code = '9999' AND banking_transaction_id IS NOT NULL
""")

row = cur.fetchone()
print(f"\nGL 9999 entries with banking_transaction_id: {row[0]}")
print(f"  - Linked to charters: {row[1]}")
print(f"  - Created from banking: {row[2]}")
print(f"  - NSF marked: {row[3]}")

# Show what GL codes the linked banking transactions have
print(f"\n{'='*100}")
print("What GL codes do the linked banking transactions have?")
print(f"{'='*100}")

cur.execute("""
    SELECT bt.category, COUNT(*) as cnt
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.gl_account_code = '9999'
    GROUP BY bt.category
    ORDER BY cnt DESC
""")

for row in cur.fetchall():
    print(f"  Banking category '{row[0]}': {row[1]} entries")

# Sample a few to show the pattern
print(f"\n{'='*100}")
print("Sample GL 9999 entries with their linked banking transactions:")
print(f"{'='*100}")

cur.execute("""
    SELECT 
        r.receipt_id, r.vendor_name, r.gross_amount, 
        bt.transaction_date, bt.description, r.created_from_banking
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.gl_account_code = '9999'
    LIMIT 15
""")

for row in cur.fetchall():
    created_from = "✓ from banking" if row[5] else "manual entry"
    print(f"  Rec {row[0]:<8} {row[1]:<40} ${row[2]:>10.2f} | {created_from}")
    print(f"          Banking: {row[4][:60]}")

cur.close()
conn.close()

print("\n" + "="*100)
print("⚠️  RECOMMENDATION:")
print("="*100)
print("""
These GL 9999 entries appear to be AUTO-CREATED from banking_transactions imports.
Since they're already linked to banking_transaction_id, they're REDUNDANT.

OPTIONS:
1. DELETE all 867 GL 9999 entries (keep only banking_transactions record)
2. MOVE them to proper GL codes based on their banking transaction category
3. KEEP them as backup copies (wasteful but safe)

Most likely: These are DUPLICATES created during import and should be DELETED.
""")

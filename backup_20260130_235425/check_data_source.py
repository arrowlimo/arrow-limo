#!/usr/bin/env python3
"""Check if the two large checks are from QuickBooks or banking data."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 100)
print("CHECK DATA SOURCE VERIFICATION")
print("=" * 100 + "\n")

for trans_id, name in [(60389, "Check #955.46"), (60330, "Check WO -120.00")]:
    cur.execute("""
        SELECT transaction_id, transaction_date, description, 
               source_file, import_batch, verified, locked,
               created_at, updated_at
        FROM banking_transactions
        WHERE transaction_id = %s
    """, (trans_id,))
    
    result = cur.fetchone()
    if result:
        tid, date, desc, source_file, import_batch, verified, locked, created, updated = result
        
        print(f"\n{name} (Transaction {tid})")
        print("-" * 100)
        print(f"Date: {date}")
        print(f"Description: {desc}")
        print(f"Source File: {source_file}")
        print(f"Import Batch: {import_batch}")
        print(f"Verified: {verified}")
        print(f"Locked: {locked}")
        print(f"Created: {created}")
        print(f"Updated: {updated}")
        
        if source_file:
            print(f"\n⚠️  Source file indicates this came from: {source_file}")
            if 'QB' in source_file.upper() or 'QUICK' in source_file.upper():
                print("   → This appears to be from QuickBooks")
            elif 'PDF' in source_file.upper() or 'BANK' in source_file.upper():
                print("   → This appears to be from banking PDF")
            else:
                print("   → Source unclear")
        else:
            print("\n⚠️  No source file recorded - data origin unknown")
        
        if not verified:
            print("   → NOT verified")
        if not locked:
            print("   → NOT locked")

print("\n" + "=" * 100)
print("2012 DATA IMPORT SUMMARY")
print("=" * 100 + "\n")

# Check all 2012 transactions for verification status
cur.execute("""
    SELECT verified, locked, COUNT(*) as count, SUM(COALESCE(debit_amount, 0) + COALESCE(credit_amount, 0)) as total
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY verified, locked
    ORDER BY verified DESC, locked DESC
""")

print("2012 Transaction Verification Status:\n")
for verified, locked, count, total in cur.fetchall():
    status = f"Verified={verified}, Locked={locked}"
    print(f"  {status:30} | {count:5d} tx | ${float(total):12,.2f}")

cur.close()
conn.close()

print("\n✅ Analysis complete")

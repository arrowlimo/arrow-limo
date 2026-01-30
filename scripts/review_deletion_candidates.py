#!/usr/bin/env python3
"""Review clear deletion candidates in detail."""

import psycopg2
import os

# Database connection
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

# Check for clear deletion candidates
print("=" * 100)
print("CLEAR DELETION CANDIDATES - DETAILED REVIEW")
print("=" * 100)

# 1. JOURNAL ENTRY (should be 3 records)
print("\n1. JOURNAL ENTRY Receipts:")
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, gl_account_code, receipt_date, description
    FROM receipts
    WHERE vendor_name = 'JOURNAL ENTRY'
    ORDER BY receipt_id
""")
journal_entries = cur.fetchall()
print(f"   Found: {len(journal_entries)} records")
for r in journal_entries:
    print(f"   - Receipt {r[0]}: {r[1]} | Amount: ${r[2]:,.2f} | GL: {r[3]} | Date: {r[4]}")

# 2. HEFFNER NULL AMOUNT
print("\n2. HEFFNER NULL AMOUNT (Duplicates):")
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, gl_account_code, receipt_date, description
    FROM receipts
    WHERE vendor_name LIKE 'HEFFNER%' AND gross_amount IS NULL
    ORDER BY receipt_id
""")
heffner_null = cur.fetchall()
print(f"   Found: {len(heffner_null)} records")
for r in heffner_null[:5]:  # Show first 5
    print(f"   - Receipt {r[0]}: {r[1]} | Amount: {r[2]} | GL: {r[3]} | Date: {r[4]}")
if len(heffner_null) > 5:
    print(f"   ... and {len(heffner_null) - 5} more")

# 3. OPENING BALANCE
print("\n3. OPENING BALANCE Receipts:")
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, gl_account_code, receipt_date, description
    FROM receipts
    WHERE vendor_name = 'OPENING BALANCE'
    ORDER BY receipt_id
""")
opening_bal = cur.fetchall()
print(f"   Found: {len(opening_bal)} records")
for r in opening_bal:
    print(f"   - Receipt {r[0]}: {r[1]} | Amount: {r[2]} | GL: {r[3]} | Date: {r[4]}")

# 4. TELUS DUPLICATE
print("\n4. TELUS [DUPLICATE - IGNORE]:")
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, gl_account_code, receipt_date, description
    FROM receipts
    WHERE vendor_name LIKE '%TELUS%DUP%' OR description LIKE '%DUPLICATE%'
    ORDER BY receipt_id
""")
telus_dup = cur.fetchall()
print(f"   Found: {len(telus_dup)} records")
for r in telus_dup[:10]:
    print(f"   - Receipt {r[0]}: {r[1]} | Amount: ${r[2]:,.2f} | GL: {r[3]} | Date: {r[4]}")
if len(telus_dup) > 10:
    print(f"   ... and {len(telus_dup) - 10} more")

# Summary
total_delete = len(journal_entries) + len(heffner_null) + len(opening_bal) + len(telus_dup)
total_amount = sum(r[2] for r in journal_entries if r[2]) + \
               sum(r[2] for r in opening_bal if r[2]) + \
               sum(r[2] for r in telus_dup if r[2])

print("\n" + "=" * 100)
print(f"TOTAL CLEAR DELETIONS: {total_delete} receipts, ${total_amount:,.2f}")
print("=" * 100)

cur.close()
conn.close()

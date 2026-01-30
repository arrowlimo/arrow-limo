#!/usr/bin/env python3
"""Check if General Journal entries were imported into Scotia banking."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("\nCHECKING GENERAL JOURNAL ENTRIES IN SCOTIA BANK")
print("="*80)

# Check for General Journal in description
cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND (
        description ILIKE '%general journal%' 
        OR description ILIKE '%gen j%'
        OR description ILIKE '%g j%'
        OR description ILIKE 'gj %'
    )
""")

result = cur.fetchone()
print(f"\n1. General Journal pattern matches:")
print(f"   Count: {result[0]}")
print(f"   Debits: ${result[1] or 0:,.2f}")
print(f"   Credits: ${result[2] or 0:,.2f}")

if result[0] > 0:
    # Show sample
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND (
            description ILIKE '%general journal%' 
            OR description ILIKE '%gen j%'
            OR description ILIKE '%g j%'
            OR description ILIKE 'gj %'
        )
        ORDER BY transaction_date
        LIMIT 10
    """)
    
    print("\n   Sample entries:")
    for row in cur.fetchall():
        tid, tdate, desc, debit, credit = row
        amt = debit or credit or 0
        direction = "DR" if debit else "CR"
        print(f"   {tdate} | ${amt:>10.2f} {direction} | {desc[:60]}")

# Check receipts created from Scotia banking
cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE mapped_bank_account_id = 2
    AND created_from_banking = TRUE
    AND (
        vendor_name ILIKE '%general journal%' 
        OR vendor_name ILIKE '%gen j%'
        OR description ILIKE '%general journal%'
        OR description ILIKE '%gen j%'
    )
""")

result = cur.fetchone()
print(f"\n2. Receipts created from General Journal banking:")
print(f"   Count: {result[0]}")
print(f"   Total: ${result[1] or 0:,.2f}")

if result[0] > 0:
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            category
        FROM receipts
        WHERE mapped_bank_account_id = 2
        AND created_from_banking = TRUE
        AND (
            vendor_name ILIKE '%general journal%' 
            OR vendor_name ILIKE '%gen j%'
            OR description ILIKE '%general journal%'
            OR description ILIKE '%gen j%'
        )
        ORDER BY receipt_date
        LIMIT 10
    """)
    
    print("\n   Sample receipts:")
    for row in cur.fetchall():
        rid, rdate, vendor, amt, cat = row
        print(f"   {rdate} | ${amt:>10.2f} | {cat:20} | {vendor[:40]}")

# Check all Scotia receipts by category
print(f"\n3. Scotia receipts category breakdown:")
cur.execute("""
    SELECT 
        category,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE mapped_bank_account_id = 2
    AND created_from_banking = TRUE
    GROUP BY category
    ORDER BY total DESC
""")

for row in cur.fetchall():
    cat, count, total = row
    print(f"   {cat:30} | {count:5,} receipts | ${total:>12,.2f}")

cur.close()
conn.close()

#!/usr/bin/env python3
"""Categorize high-value receipts with identifiable bulk patterns."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*80)
print("BULK PATTERN CATEGORIZATION")
print("="*80)

# Charter Service = Charter Revenue (Income)
cur.execute("""
    UPDATE receipts
    SET category = 'charter_revenue',
        gl_account_code = '4100',
        auto_categorized = TRUE
    WHERE vendor_name LIKE '%Charter_Service%'
    AND gl_account_code IS NULL
""")
charter_count = cur.rowcount
print(f"✓ Categorized {charter_count} Charter Service receipts → 4100 Charter Revenue")

# Branch withdrawals = Owner's Draws (Equity)
cur.execute("""
    UPDATE receipts
    SET category = 'owner_draws',
        gl_account_code = '3200',
        auto_categorized = TRUE
    WHERE (description LIKE '%WITHDRAWAL%IBB%GAET%' 
           OR description LIKE '%WITHDRAWAL%03239%GA%'
           OR vendor_name LIKE '%Branch Transaction WITHDRAWAL%')
    AND gl_account_code IS NULL
""")
withdrawal_count = cur.rowcount
print(f"✓ Categorized {withdrawal_count} Branch Withdrawal receipts → 3200 Owner's Draws")

# Woodridge Ford = Vehicle purchases (Asset)
cur.execute("""
    UPDATE receipts
    SET category = 'vehicle_purchase',
        gl_account_code = '1600',
        auto_categorized = TRUE
    WHERE vendor_name LIKE '%Woodridge Ford%'
    AND gl_account_code IS NULL
    AND gross_amount > 5000
""")
vehicle_count = cur.rowcount
print(f"✓ Categorized {vehicle_count} Woodridge Ford receipts → 1600 Vehicles (Asset)")

# Generic business expenses from CIBC ledger
cur.execute("""
    UPDATE receipts
    SET category = 'uncategorized_expenses',
        gl_account_code = '5850',
        auto_categorized = TRUE
    WHERE description LIKE '%Business Expense - CIBC%'
    AND gl_account_code IS NULL
""")
cibc_count = cur.rowcount
print(f"✓ Categorized {cibc_count} CIBC Business Expense receipts → 5850 Uncategorized")

# Numeric-only vendor names (6-digit format like 008815) - likely cheque numbers
cur.execute("""
    UPDATE receipts
    SET category = 'cheque_payment',
        gl_account_code = '5850',
        auto_categorized = TRUE
    WHERE vendor_name ~ '^[0-9]{6}$'
    AND gl_account_code IS NULL
""")
cheque_count = cur.rowcount
print(f"✓ Categorized {cheque_count} numeric vendor receipts → 5850 (likely cheques)")

conn.commit()

total = charter_count + withdrawal_count + vehicle_count + cibc_count + cheque_count
print(f"\n✓ TOTAL: {total} receipts categorized in bulk patterns")

# Get updated stats
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN gl_account_code IS NOT NULL THEN 1 END) as with_gl
    FROM receipts
    WHERE business_personal IS NULL OR business_personal != 'personal'
""")
row = cur.fetchone()
total_receipts = row[0]
with_gl = row[1]

print("\n" + "="*80)
print(f"UPDATED STATUS: {with_gl:,}/{total_receipts:,} receipts ({with_gl*100/total_receipts:.1f}%)")
print("="*80)

conn.close()

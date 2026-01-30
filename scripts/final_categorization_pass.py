#!/usr/bin/env python3
"""Final categorization pass for remaining patterns."""

import psycopg2
import re

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("="*80)
print("FINAL CATEGORIZATION PASS")
print("="*80)

categorized = 0

# credit_card vendor = credit card payments (liability reduction)
cur.execute("""
    UPDATE receipts
    SET category = 'credit_card_payment',
        gl_account_code = '2100',
        auto_categorized = TRUE
    WHERE vendor_name = 'credit_card'
    AND gl_account_code IS NULL
""")
count = cur.rowcount
print(f"✓ {count} credit_card payments → 2100 Credit Card Liability")
categorized += count

# RBC bank transactions = bank transfers (asset)
cur.execute("""
    UPDATE receipts
    SET category = 'internal_transfer',
        gl_account_code = '1010',
        auto_categorized = TRUE
    WHERE vendor_name = 'RBC'
    AND gl_account_code IS NULL
""")
count = cur.rowcount
print(f"✓ {count} RBC transactions → 1010 Internal Transfer")
categorized += count

# TD bank transactions = bank transfers
cur.execute("""
    UPDATE receipts
    SET category = 'internal_transfer',
        gl_account_code = '1010',
        auto_categorized = TRUE
    WHERE vendor_name = 'TD'
    AND gl_account_code IS NULL
""")
count = cur.rowcount
print(f"✓ {count} TD transactions → 1010 Internal Transfer")
categorized += count

# Point of Sale without vendor details = uncategorized expenses
cur.execute("""
    UPDATE receipts
    SET category = 'uncategorized_expenses',
        gl_account_code = '5850',
        auto_categorized = TRUE
    WHERE (vendor_name LIKE 'Point of Sale%' 
           OR description LIKE '%Point of Sale%')
    AND gl_account_code IS NULL
""")
count = cur.rowcount
print(f"✓ {count} Point of Sale receipts → 5850 Uncategorized Expenses")
categorized += count

# Bank Charges & Interest = bank fees
cur.execute("""
    UPDATE receipts
    SET category = 'bank_fees',
        gl_account_code = '5150',
        auto_categorized = TRUE
    WHERE (vendor_name LIKE '%Bank Charges%' 
           OR vendor_name LIKE '%NON-SUFFICIENT FUNDS%'
           OR vendor_name LIKE '%ACC FEE%')
    AND gl_account_code IS NULL
""")
count = cur.rowcount
print(f"✓ {count} bank fee receipts → 5150 Bank Fees")
categorized += count

# Automated Banking Machine = cash withdrawals (petty cash)
cur.execute("""
    UPDATE receipts
    SET category = 'petty_cash',
        gl_account_code = '1020',
        auto_categorized = TRUE
    WHERE vendor_name LIKE '%Automated Banking Machine%'
    AND gl_account_code IS NULL
""")
count = cur.rowcount
print(f"✓ {count} ABM withdrawals → 1020 Petty Cash")
categorized += count

# Co-op gas stations
cur.execute("""
    UPDATE receipts
    SET category = 'fuel',
        gl_account_code = '5110',
        auto_categorized = TRUE
    WHERE vendor_name LIKE '%Co-op%'
    AND gl_account_code IS NULL
""")
count = cur.rowcount
print(f"✓ {count} Co-op receipts → 5110 Fuel")
categorized += count

# RCSS (Real Canadian Superstore) - supplies
cur.execute("""
    UPDATE receipts
    SET category = 'supplies',
        gl_account_code = '5430',
        auto_categorized = TRUE
    WHERE vendor_name = 'RCSS'
    AND gl_account_code IS NULL
""")
count = cur.rowcount
print(f"✓ {count} RCSS receipts → 5430 Supplies")
categorized += count

# Charter_2015/2016 individual entries = charter revenue
cur.execute("""
    UPDATE receipts
    SET category = 'charter_revenue',
        gl_account_code = '4100',
        auto_categorized = TRUE
    WHERE (vendor_name LIKE 'Charter_2015_%' 
           OR vendor_name LIKE 'Charter_2016_%'
           OR vendor_name LIKE 'Charter_2013_%'
           OR vendor_name LIKE 'Charter_2014_%')
    AND gl_account_code IS NULL
""")
count = cur.rowcount
print(f"✓ {count} individual charter entries → 4100 Charter Revenue")
categorized += count

# Woodridge Ford (small amounts) = maintenance
cur.execute("""
    UPDATE receipts
    SET category = 'maintenance',
        gl_account_code = '5120',
        auto_categorized = TRUE
    WHERE vendor_name LIKE '%Woodridge Ford%'
    AND gross_amount < 5000
    AND gl_account_code IS NULL
""")
count = cur.rowcount
print(f"✓ {count} Woodridge Ford maintenance → 5120 Vehicle Maintenance")
categorized += count

conn.commit()

print(f"\n✓ TOTAL: {categorized} receipts categorized")

# Final stats
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN gl_account_code IS NOT NULL THEN 1 END) as with_gl
    FROM receipts
    WHERE business_personal IS NULL OR business_personal != 'personal'
""")
row = cur.fetchone()
total = row[0]
with_gl = row[1]

print("\n" + "="*80)
print(f"FINAL STATUS: {with_gl:,}/{total:,} receipts ({with_gl*100/total:.1f}%)")
print("="*80)

conn.close()

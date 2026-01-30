#!/usr/bin/env python3
"""Verify final state after 'do all' completion."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("="*80)
print("FINAL VERIFICATION - 'DO ALL' COMPLETION")
print("="*80)

# 1. Receipt categorization status
print("\n1. Receipt Categorization Status")
print("-"*80)

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN gl_account_code IS NOT NULL THEN 1 END) as with_gl_code,
        COUNT(CASE WHEN auto_categorized = TRUE THEN 1 END) as auto_categorized
    FROM receipts
    WHERE business_personal IS NULL OR business_personal != 'personal'
""")

row = cur.fetchone()
total = row[0]
with_gl = row[1]
auto_cat = row[2]

print(f"  Business Receipts: {total:,}")
print(f"  With GL Code: {with_gl:,} ({with_gl*100/total:.1f}%)")
print(f"  Auto-Categorized: {auto_cat:,} ({auto_cat*100/total:.1f}%)")

# 2. Receipt system tables
print("\n2. Advanced Receipt System Tables")
print("-"*80)

tables = ['receipt_line_items', 'vendor_default_categories', 'cash_box_transactions', 'driver_floats']
for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"  ✓ {table}: {count} rows")

# 3. Chart of accounts
print("\n3. Chart of Accounts")
print("-"*80)

cur.execute("SELECT COUNT(*) FROM chart_of_accounts")
count = cur.fetchone()[0]
print(f"  Total accounts: {count}")

cur.execute("""
    SELECT 
        SUBSTRING(account_code FROM 1 FOR 1) as category_prefix,
        CASE 
            WHEN account_code ~ '^1' THEN 'Assets'
            WHEN account_code ~ '^2' THEN 'Liabilities'
            WHEN account_code ~ '^3' THEN 'Equity'
            WHEN account_code ~ '^4' THEN 'Income'
            WHEN account_code ~ '^5' THEN 'Expenses'
            ELSE 'Other'
        END as category,
        COUNT(*) 
    FROM chart_of_accounts 
    GROUP BY category_prefix, category
    ORDER BY category_prefix
""")

for row in cur.fetchall():
    print(f"    {row[1]}: {row[2]} accounts")

# 4. Category mapping
print("\n4. Category Mapping System")
print("-"*80)

cur.execute("SELECT COUNT(*) FROM category_to_account_map")
count = cur.fetchone()[0]
print(f"  Category → GL mappings: {count}")

cur.execute("""
    SELECT COUNT(*) 
    FROM account_categories 
    WHERE gl_account_code IS NOT NULL
""")
count = cur.fetchone()[0]
print(f"  Categories with GL codes: {count} of 33")

# 5. Database cleanup results
print("\n5. Database Cleanup Results")
print("-"*80)

cur.execute("""
    SELECT COUNT(*) 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND (
        table_name LIKE '%account%' 
        OR table_name LIKE '%receipt%'
        OR table_name LIKE '%banking%'
        OR table_name LIKE '%journal%'
        OR table_name LIKE '%ledger%'
    )
    AND table_name NOT LIKE '%backup%'
""")
accounting_tables = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%backup%'
""")
backup_tables = cur.fetchone()[0]

print(f"  Accounting-related tables: {accounting_tables}")
print(f"  Backup tables: {backup_tables}")

# 6. Smart categorization results by account
print("\n6. Recent Auto-Categorization Results (Top 5)")
print("-"*80)

cur.execute("""
    SELECT 
        gl_account_code,
        a.account_name,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts r
    LEFT JOIN chart_of_accounts a ON r.gl_account_code = a.account_code
    WHERE auto_categorized = TRUE
    GROUP BY gl_account_code, a.account_name
    ORDER BY COUNT(*) DESC
    LIMIT 5
""")

for row in cur.fetchall():
    code = row[0] or 'NULL'
    name = row[1] or 'Unknown'
    count = row[2]
    total = float(row[3]) if row[3] else 0
    print(f"  {code} - {name}: {count} receipts (${total:,.2f})")

print("\n" + "="*80)
print("✓ VERIFICATION COMPLETE")
print("="*80)

conn.close()

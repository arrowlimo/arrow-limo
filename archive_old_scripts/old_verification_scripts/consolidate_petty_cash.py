#!/usr/bin/env python3
"""Consolidate duplicate Petty Cash GL accounts."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='ArrowLimousine',
    dbname='almsdata'
)
cur = conn.cursor()

print("\n" + "="*100)
print("CONSOLIDATE PETTY CASH ACCOUNTS")
print("="*100)

# Check current status
print("\n1. Current Petty Cash accounts:")
print("-"*100)

cur.execute("""
    SELECT 
        c.account_code,
        c.account_name,
        COUNT(r.receipt_id) as receipt_count,
        SUM(r.gross_amount) as total_amount
    FROM chart_of_accounts c
    LEFT JOIN receipts r ON r.gl_account_code = c.account_code
    WHERE c.account_name ILIKE '%petty%cash%'
    GROUP BY c.account_code, c.account_name
    ORDER BY c.account_code
""")

petty_cash_accounts = cur.fetchall()

print(f"{'GL Code':<10} {'Name':<30} {'Receipts':<10} {'Amount'}")
print("-"*100)

for code, name, count, amount in petty_cash_accounts:
    amount_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"{code:<10} {name:<30} {count:<10} {amount_str}")

# Decision: Keep GL 1015, move everything from 1030
print("\n2. Consolidating to GL 1015 (standard GL numbering)...")
print("-"*100)

# Move receipts from 1030 to 1015
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '1015',
        gl_account_name = 'Petty Cash'
    WHERE gl_account_code = '1030'
""")

moved_receipts = cur.rowcount
print(f"✓ Moved {moved_receipts} receipts from GL 1030 to GL 1015")

# Deactivate GL 1030
cur.execute("""
    UPDATE chart_of_accounts
    SET is_active = FALSE,
        account_name = 'Petty Cash (INACTIVE - Consolidated to 1015)'
    WHERE account_code = '1030'
""")

print("✓ Deactivated GL 1030")

# Ensure GL 1015 has correct name
cur.execute("""
    UPDATE chart_of_accounts
    SET account_name = 'Petty Cash',
        is_active = TRUE
    WHERE account_code = '1015'
""")

print("✓ Updated GL 1015 name")

conn.commit()

# 3. Verification
print("\n3. Verification:")
print("-"*100)

cur.execute("""
    SELECT 
        c.account_code,
        c.account_name,
        c.is_active,
        COUNT(r.receipt_id) as receipt_count,
        SUM(r.gross_amount) as total_amount
    FROM chart_of_accounts c
    LEFT JOIN receipts r ON r.gl_account_code = c.account_code
    WHERE c.account_code IN ('1015', '1030')
    GROUP BY c.account_code, c.account_name, c.is_active
    ORDER BY c.account_code
""")

final_status = cur.fetchall()

print(f"{'GL Code':<10} {'Name':<45} {'Active':<8} {'Receipts':<10} {'Amount'}")
print("-"*100)

for code, name, active, count, amount in final_status:
    name_display = (name or "")[:45]
    active_str = "Yes" if active else "No"
    amount_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"{code:<10} {name_display:<45} {active_str:<8} {count:<10} {amount_str}")

print("\n" + "="*100)
print("COMPLETE")
print("="*100)
print(f"""
✓ Consolidated duplicate Petty Cash accounts
✓ All petty cash now under GL 1015
✓ GL 1030 deactivated (no longer in use)
✓ {moved_receipts} receipts moved to proper GL code
""")

conn.close()

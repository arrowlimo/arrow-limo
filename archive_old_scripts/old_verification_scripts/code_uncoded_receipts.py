#!/usr/bin/env python3
"""Review and code uncoded receipts."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='ArrowLimousine',
    dbname='almsdata'
)
cur = conn.cursor()

print("\n" + "="*100)
print("CODING UNCODED RECEIPTS")
print("="*100)

# 1. Charter Payment receipts - these should be revenue, not expenses
print("\n1. Charter Payment entries...")
print("-"*100)

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name = 'Charter Payment'
    AND (gl_account_code IS NULL OR gl_account_code = '')
""")

charter_count, charter_amount = cur.fetchone()
print(f"Found {charter_count} Charter Payment receipts (${charter_amount:,.2f})")
print("These should be recorded as charter REVENUE (GL 4100), not receipts/expenses")
print("Action: Delete these as they're duplicate revenue entries")

cur.execute("""
    DELETE FROM receipts
    WHERE vendor_name = 'Charter Payment'
    AND (gl_account_code IS NULL OR gl_account_code = '')
""")

deleted_charters = cur.rowcount
print(f"✓ Deleted {deleted_charters} duplicate charter payment receipts")

# 2. BANKING TRANSACTION entries
print("\n2. Banking Transaction entries...")
print("-"*100)

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name = 'BANKING TRANSACTION'
    AND (gl_account_code IS NULL OR gl_account_code = '')
""")

banking_count, banking_amount = cur.fetchone()
print(f"Found {banking_count} BANKING TRANSACTION receipts (${banking_amount:,.2f})")
print("These are internal transfers or reconciliation entries")

# Code as bank fees/transfers
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '5710',
        gl_account_name = 'Bank Fees & Service Charges'
    WHERE vendor_name = 'BANKING TRANSACTION'
    AND (gl_account_code IS NULL OR gl_account_code = '')
    AND gross_amount > 0
""")

banking_updated = cur.rowcount
print(f"✓ Coded {banking_updated} banking transactions to GL 5710")

# 3. Other uncoded receipts
print("\n3. Other uncoded receipts...")
print("-"*100)

cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE (gl_account_code IS NULL OR gl_account_code = '')
    GROUP BY vendor_name
    ORDER BY count DESC
""")

remaining = cur.fetchall()
if remaining:
    print(f"{'Vendor':<40} {'Count':<10} {'Amount'}")
    print("-"*100)
    for vendor, count, total in remaining:
        vendor_display = (vendor or "BLANK")[:40]
        total_str = f"${total:,.2f}" if total else "$0.00"
        print(f"{vendor_display:<40} {count:<10} {total_str}")
        
        # Code based on vendor name
        if vendor:
            if 'liquor' in vendor.lower():
                cur.execute("""
                    UPDATE receipts
                    SET gl_account_code = '5116',
                        gl_account_name = 'Client Amenities - Food, Coffee, Supplies'
                    WHERE vendor_name = %s
                    AND (gl_account_code IS NULL OR gl_account_code = '')
                """, (vendor,))
                if cur.rowcount > 0:
                    print(f"  → Coded to 5116 (Client Amenities)")
            
            elif any(x in vendor.lower() for x in ['shell', 'esso', 'petro', 'gas']):
                cur.execute("""
                    UPDATE receipts
                    SET gl_account_code = '5200',
                        gl_account_name = 'Driver & Payroll Expenses'
                    WHERE vendor_name = %s
                    AND (gl_account_code IS NULL OR gl_account_code = '')
                """, (vendor,))
                if cur.rowcount > 0:
                    print(f"  → Coded to 5200 (Fuel)")
else:
    print("✓ No remaining uncoded receipts!")

conn.commit()

# 4. Final summary
print("\n" + "="*100)
print("FINAL STATUS")
print("="*100)

cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code IS NULL OR gl_account_code = ''")
final_uncoded = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code IS NOT NULL AND gl_account_code != ''")
final_coded = cur.fetchone()[0]

print(f"""
✓ Deleted {deleted_charters} duplicate charter payment entries
✓ Coded {banking_updated} banking transaction receipts
✓ Remaining uncoded: {final_uncoded}
✓ Total coded: {final_coded:,}
✓ Coding completion: {(final_coded/(final_coded+final_uncoded)*100):.1f}%
""")

conn.close()

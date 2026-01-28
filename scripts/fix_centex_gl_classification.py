#!/usr/bin/env python3
"""
Fix Centex receipts misclassified to GL 5200 (Driver & Payroll Expenses).
Centex is a fuel vendor and should use GL 5110 (Fuel Expense).
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Show current state
print("=" * 80)
print("CENTEX GL CLASSIFICATION AUDIT")
print("=" * 80)

cur.execute("""
    SELECT COUNT(*), gl_account_code, gl_account_name
    FROM receipts
    WHERE vendor_name ILIKE '%CENTEX%'
    GROUP BY gl_account_code, gl_account_name
    ORDER BY COUNT(*) DESC
""")

rows = cur.fetchall()
print("\nCurrent Centex classifications:")
total_centex = 0
for r in rows:
    gl_code = r[1] or "NULL"
    gl_name = r[2] or "N/A"
    print(f"  {r[0]:4d} receipts → GL {gl_code:10} | {gl_name}")
    total_centex += r[0]

print(f"\nTotal Centex receipts: {total_centex}")

# Count misclassified (not 5110 fuel)
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name ILIKE '%CENTEX%' AND gl_account_code != '5110'
""")
wrong_count = cur.fetchone()[0]
print(f"❌ {wrong_count} receipts with wrong GL code (not 5110)")

if wrong_count > 0:
    print("\nShowing sample misclassified receipts:")
    cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, gl_account_code, gl_account_name
        FROM receipts
        WHERE vendor_name ILIKE '%CENTEX%' AND gl_account_code != '5110'
        ORDER BY receipt_date DESC
        LIMIT 5
    """)
    for r in cur.fetchall():
        print(f"  Receipt {r[0]:6d} | {r[1]} | ${r[2]:8.2f} | GL {r[3]:10} | {r[4]}")

    # FIX: Update all Centex to GL 5110
    print("\n" + "=" * 80)
    print("APPLYING FIX: Set all Centex receipts to GL 5110 (Fuel Expense)")
    print("=" * 80)
    
    cur.execute("""
        UPDATE receipts
        SET gl_account_code = '5110',
            gl_account_name = 'Vehicle Fuel'
        WHERE vendor_name ILIKE '%CENTEX%' AND gl_account_code != '5110'
    """)
    
    fixed_count = cur.rowcount
    conn.commit()
    
    print(f"✅ Fixed {fixed_count} receipts")
    
    # Verify
    print("\nVerification after fix:")
    cur.execute("""
        SELECT COUNT(*), gl_account_code, gl_account_name
        FROM receipts
        WHERE vendor_name ILIKE '%CENTEX%'
        GROUP BY gl_account_code, gl_account_name
        ORDER BY COUNT(*) DESC
    """)
    
    for r in cur.fetchall():
        gl_code = r[1] or "NULL"
        gl_name = r[2] or "N/A"
        print(f"  {r[0]:4d} receipts → GL {gl_code:10} | {gl_name}")
else:
    print("\n✅ All Centex receipts are already correctly classified to GL 5110")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("Done!")
print("=" * 80)

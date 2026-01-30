#!/usr/bin/env python3
"""Delete truly bogus orphan receipts from 2020-2025 (excluding legitimate accruals)."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 100)
print("DELETE BOGUS ORPHAN RECEIPTS (2020-2025)")
print("=" * 100)

# Get list of deletable receipts
print("\nIDENTIFYING BOGUS RECEIPTS:")
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, receipt_date
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
    AND banking_transaction_id IS NULL
    AND vendor_name NOT LIKE '%HEFFNER%'
    AND vendor_name NOT LIKE '%CMB%INSURANCE%'
    AND vendor_name NOT LIKE '%TD%INSURANCE%'
    ORDER BY receipt_date, vendor_name
""")
deletable = cur.fetchall()

print(f"\nFound {len(deletable)} bogus orphan receipts:")
print(f"{'Date':<12} {'Vendor':<50} {'Amount':>12} {'Receipt ID':>10}")
print("-" * 100)

total_amount = 0
for rid, vendor, amount, rdate in deletable:
    amt_str = f"${amount:,.2f}" if amount else "NULL"
    vendor_display = vendor[:47] + "..." if len(vendor) > 50 else vendor
    print(f"{str(rdate):<12} {vendor_display:<50} {amt_str:>12} {rid:>10}")
    total_amount += amount if amount else 0

print(f"\n{'TOTAL':<62} ${total_amount:>12,.2f} {len(deletable):>10} receipts")

print("\n" + "=" * 100)
print("DELETION PREVIEW")
print("=" * 100)
print(f"""
This will DELETE {len(deletable)} receipts totaling ${total_amount:,.2f}

These receipts:
  ✓ Have NO banking transaction link
  ✓ Are from 2020-2025 (accurate banking period)
  ✓ Exclude Heffner (legitimate accruals)
  ✓ Exclude Insurance (legitimate premiums)

KEPT (NOT deleted):
  - HEFFNER AUTO FINANCE: 1,259 receipts (vehicle finance accruals)
  - CMB/TD INSURANCE: 5 receipts (insurance premiums)

Proceed with deletion? [YES/NO]: """)

response = input().strip().upper()
if response != "YES":
    print("\n❌ Deletion cancelled by user")
    cur.close()
    conn.close()
    exit(0)

# Execute deletion
print("\n" + "=" * 100)
print("EXECUTING DELETION...")
print("=" * 100)

try:
    cur.execute("""
        DELETE FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2020 AND 2025
        AND banking_transaction_id IS NULL
        AND vendor_name NOT LIKE '%HEFFNER%'
        AND vendor_name NOT LIKE '%CMB%INSURANCE%'
        AND vendor_name NOT LIKE '%TD%INSURANCE%'
    """)
    
    deleted_count = cur.rowcount
    conn.commit()
    
    print(f"✅ Successfully deleted {deleted_count} receipts")
    
    # Verify
    cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts")
    final_count, final_amount = cur.fetchone()
    print(f"\nFinal receipt count: {final_count:,} receipts, ${final_amount:,.2f}")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Deletion failed: {e}")

cur.close()
conn.close()

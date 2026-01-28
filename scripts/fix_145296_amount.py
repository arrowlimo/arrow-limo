#!/usr/bin/env python3
"""
Fix Receipt 145296 - should be $686.65 not $1,126.80
"""

import psycopg2, os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("="*70)
print("FIXING RECEIPT 145296")
print("="*70)

# Show current value
cur.execute("""
    SELECT receipt_id, receipt_date, source_reference, gross_amount, fiscal_year, description
    FROM receipts
    WHERE receipt_id = 145296
""")
row = cur.fetchone()
print(f"\nBEFORE: Receipt {row[0]} | {row[1]} | {row[2]} | ${row[3]:,.2f} | FY{row[4]}")
print(f"        {row[5]}")

# Update amount from $1,126.80 to $686.65
cur.execute("""
    UPDATE receipts
    SET gross_amount = 686.65
    WHERE receipt_id = 145296
    RETURNING receipt_id, gross_amount
""")
updated = cur.fetchone()
print(f"\n✅ UPDATED: Receipt {updated[0]} | gross_amount = ${updated[1]:,.2f}")

conn.commit()

# Verify final counts
cur.execute("""
    SELECT 
        fiscal_year,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE vendor_name = 'WCB' AND gross_amount > 0
    GROUP BY fiscal_year
    ORDER BY fiscal_year
""")

print("\n" + "="*70)
print("FINAL WCB INVOICE COUNTS BY FISCAL YEAR")
print("="*70)

for row in cur.fetchall():
    fy, count, total = row
    print(f"  FY{fy}: {count} invoices = ${total:,.2f}")

print("\nEXPECTED:")
print("  FY2011: 1 invoice = $686.65")
print("  FY2012: 13 invoices = $4,593.00")

conn.close()

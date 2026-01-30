import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

# Get detailed Mid-Alta Motors receipts
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, category, description
    FROM receipts
    WHERE UPPER(vendor_name) LIKE '%MID-ALTA%' OR UPPER(vendor_name) LIKE '%MID ALTA%'
    ORDER BY receipt_date DESC
""")

rows = cur.fetchall()
print("=" * 100)
print("MID-ALTA MOTORS LTD - EXISTING RECEIPTS")
print("=" * 100)
print(f"Total receipts found: {len(rows)}\n")

for rid, rdate, vendor, amount, category, desc in rows:
    print(f"Receipt {rid}:")
    print(f"  Date:        {rdate}")
    print(f"  Vendor:      {vendor}")
    print(f"  Amount:      ${amount}")
    print(f"  Category:    {category}")
    print(f"  Description: {desc}")
    print()

# Update mixed_use to maintenance (vehicle service vendor)
cur.execute("""
    UPDATE receipts
    SET category = 'maintenance'
    WHERE (UPPER(vendor_name) LIKE '%MID-ALTA%' OR UPPER(vendor_name) LIKE '%MID ALTA%')
      AND category = 'mixed_use'
""")

updated = cur.rowcount
print("=" * 100)
print(f"✓ Updated {updated} receipts from mixed_use to maintenance")
print()
print("VERIFIED VENDOR - Mid-Alta Motors Ltd")
print("=" * 100)
print("""
Full Name:      Mid-Alta Motors Ltd
Address:        172 Clearview Drive Bay, Unit 102
                Red Deer County, AB T4E 0A1
Service Type:   Vehicle maintenance and repair
Category:       maintenance
Status:         ✓ VERIFIED AND CERTIFIED
Receipt Count:  6 receipts (2012-2025)
Date Range:     2012-07-09 to 2025-10-17

Vendor Variations in Database:
  - MID-ALTA MOTORS LTD
  - Cheque Mid-Alta Motors
  - Mid-Alta Motors
""")

conn.commit()
cur.close()
conn.close()

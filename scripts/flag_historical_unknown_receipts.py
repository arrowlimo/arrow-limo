#!/usr/bin/env python3
"""
Flag pre-2012 UNKNOWN receipts as historical (unverified period).
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 80)
print("FLAGGING HISTORICAL UNKNOWN RECEIPTS (PRE-2012)")
print("=" * 80)

# Check current UNKNOWN receipts
cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        gross_amount,
        description,
        category
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
    ORDER BY receipt_date
""")

rows = cur.fetchall()
print(f"\nFound {len(rows)} UNKNOWN receipts:")
print("\nDate       | Amount    | Category          | Description")
print("-" * 80)
for r_id, r_date, amount, desc, cat in rows:
    amt_str = f"${amount:,.2f}" if amount else "$0.00"
    desc_str = (desc or '')[:25]
    cat_str = (cat or 'None')[:17]
    print(f"{r_date} | {amt_str:9} | {cat_str:17} | {desc_str}")

# Update to HISTORICAL category
print("\n" + "=" * 80)
print("UPDATING TO HISTORICAL CATEGORY")
print("=" * 80)

cur.execute("""
    UPDATE receipts
    SET category = 'HISTORICAL - UNVERIFIED',
        vendor_name = 'HISTORICAL - UNVERIFIED'
    WHERE vendor_name = 'UNKNOWN'
      AND receipt_date < '2012-01-01'
""")

updated = cur.rowcount
conn.commit()
print(f"\n✅ Updated {updated} receipts to HISTORICAL - UNVERIFIED")

# Verify
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
""")
remaining_unknown = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name = 'HISTORICAL - UNVERIFIED'
""")
historical_count = cur.fetchone()[0]

print("\n" + "=" * 80)
print("FINAL STATUS")
print("=" * 80)
print(f"\nRemaining UNKNOWN: {remaining_unknown}")
print(f"HISTORICAL - UNVERIFIED: {historical_count}")

if historical_count > 0:
    cur.execute("""
        SELECT 
            receipt_date,
            gross_amount,
            description
        FROM receipts
        WHERE vendor_name = 'HISTORICAL - UNVERIFIED'
        ORDER BY receipt_date
    """)
    
    print("\nHistorical receipts (pre-2012, unverified period):")
    print("Date       | Amount    | Description")
    print("-" * 60)
    for r_date, amount, desc in cur.fetchall():
        amt_str = f"${amount:,.2f}" if amount else "$0.00"
        desc_str = (desc or '')[:35]
        print(f"{r_date} | {amt_str:9} | {desc_str}")

cur.close()
conn.close()

print("\n✅ COMPLETE")

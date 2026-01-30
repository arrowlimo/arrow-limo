#!/usr/bin/env python3
"""
Check year distribution of UNKNOWN receipts before deletion.
Protect 2019 manually entered receipts.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

print("=" * 80)
print("CHECKING YEAR DISTRIBUTION OF UNKNOWN RECEIPTS")
print("=" * 80)

# Check duplicates by year
cur.execute("""
    WITH duplicates AS (
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.gross_amount,
            r.description,
            EXTRACT(YEAR FROM r.receipt_date) as year
        FROM receipts r
        WHERE r.vendor_name = 'UNKNOWN'
          AND r.gross_amount IS NOT NULL
          AND r.gross_amount > 0
    ),
    banking_matches AS (
        SELECT 
            d.*,
            b.transaction_id,
            m.receipt_id as matched_receipt_id
        FROM duplicates d
        INNER JOIN banking_transactions b 
            ON b.transaction_date = d.receipt_date
            AND ABS(b.debit_amount - d.gross_amount) < 0.01
        LEFT JOIN banking_receipt_matching_ledger m 
            ON b.transaction_id = m.banking_transaction_id
        WHERE m.receipt_id IS NOT NULL
          AND m.receipt_id != d.receipt_id
    )
    SELECT 
        year,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM banking_matches
    GROUP BY year
    ORDER BY year
""")

duplicate_years = cur.fetchall()

print("\nDUPLICATE RECEIPTS BY YEAR:")
print("Year | Count | Total Amount")
print("-" * 40)
total_dup = 0
for year, count, amount in duplicate_years:
    print(f"{int(year)} | {count:5} | ${amount:,.2f}")
    total_dup += count

print(f"\nTotal duplicates: {total_dup}")

# Check NULL/zero by year
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as count
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
      AND (gross_amount IS NULL OR gross_amount = 0)
    GROUP BY year
    ORDER BY year
""")

null_years = cur.fetchall()

print("\n\nNULL/ZERO AMOUNT RECEIPTS BY YEAR:")
print("Year | Count")
print("-" * 20)
total_null = 0
for year, count in null_years:
    if year:
        print(f"{int(year)} | {count:5}")
        total_null += count

print(f"\nTotal null/zero: {total_null}")

# Check 2019 specifically
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
      AND EXTRACT(YEAR FROM receipt_date) = 2019
""")
year_2019_count = cur.fetchone()[0]

print("\n" + "=" * 80)
print("2019 RECEIPTS CHECK")
print("=" * 80)
print(f"\nTotal UNKNOWN receipts from 2019: {year_2019_count}")

if year_2019_count > 0:
    print("\n⚠️  WARNING: 2019 receipts found!")
    print("   These are manually entered and should be reviewed carefully")
    
    # Show samples
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            gross_amount,
            description
        FROM receipts
        WHERE vendor_name = 'UNKNOWN'
          AND EXTRACT(YEAR FROM receipt_date) = 2019
        ORDER BY gross_amount DESC
        LIMIT 20
    """)
    
    print("\n   Sample 2019 UNKNOWN receipts:")
    print("   Date       | Amount    | Description")
    print("   " + "-" * 60)
    for row in cur.fetchall():
        r_id, r_date, amount, desc = row
        amt_str = f"${amount:,.2f}" if amount else "$0.00"
        desc_str = (desc or '')[:35]
        print(f"   {r_date} | {amt_str:9} | {desc_str}")
else:
    print("\n✅ No 2019 receipts found - safe to proceed")

# Summary
print("\n" + "=" * 80)
print("DELETION SAFETY CHECK")
print("=" * 80)

print(f"\nTotal to delete: {total_dup + total_null}")
print(f"  Duplicates: {total_dup}")
print(f"  Null/zero: {total_null}")

if year_2019_count > 0:
    print(f"\n⚠️  STOP: {year_2019_count} receipts from 2019 (manually entered)")
    print("   Recommendation: Exclude 2019 from deletion")
else:
    print("\n✅ SAFE TO DELETE: No 2019 receipts found")

cur.close()
conn.close()

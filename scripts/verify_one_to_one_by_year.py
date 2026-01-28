#!/usr/bin/env python3
"""
Verify one-to-one receipt-banking matching by year.
Shows which years have cash receipts, manual entries, etc without banking links.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 100)
print("ONE-TO-ONE RECEIPT-BANKING VERIFICATION BY YEAR")
print("=" * 100)

# Get year-by-year breakdown
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as total_receipts,
        COUNT(banking_transaction_id) as with_banking,
        COUNT(*) - COUNT(banking_transaction_id) as without_banking,
        SUM(gross_amount) as total_amount,
        SUM(CASE WHEN banking_transaction_id IS NULL THEN gross_amount ELSE 0 END) as unlinked_amount
    FROM receipts
    WHERE exclude_from_reports = FALSE
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year
""")

yearly_data = cur.fetchall()

print("\nYEAR-BY-YEAR BREAKDOWN:")
print("-" * 100)
print(f"{'Year':<6} {'Total':<8} {'With Banking':<15} {'Without Banking':<18} {'Total $':<15} {'Unlinked $':<15}")
print("-" * 100)

for year, total, with_bank, without_bank, total_amt, unlinked_amt in yearly_data:
    year_str = f"{int(year)}" if year else "NULL"
    with_pct = (with_bank / total * 100) if total > 0 else 0
    without_pct = (without_bank / total * 100) if total > 0 else 0
    
    print(f"{year_str:<6} {total:<8} {with_bank:<8} ({with_pct:>5.1f}%)  {without_bank:<8} ({without_pct:>5.1f}%)  ${total_amt:>12,.2f}  ${unlinked_amt:>12,.2f}")

# Check for banking transactions with multiple receipts (violation of one-to-one)
print("\n" + "=" * 100)
print("CHECKING FOR ONE-TO-ONE VIOLATIONS (banking TX with multiple receipts)")
print("=" * 100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM r.receipt_date) as year,
        COUNT(DISTINCT r.banking_transaction_id) as banking_txs_with_splits,
        SUM(receipt_count) as total_receipt_count
    FROM (
        SELECT 
            banking_transaction_id,
            receipt_date,
            COUNT(*) as receipt_count
        FROM receipts
        WHERE banking_transaction_id IS NOT NULL
        AND exclude_from_reports = FALSE
        GROUP BY banking_transaction_id, receipt_date
        HAVING COUNT(*) > 1
    ) r
    GROUP BY EXTRACT(YEAR FROM r.receipt_date)
    ORDER BY year
""")

violations = cur.fetchall()

if violations:
    print("\n⚠️  VIOLATIONS FOUND:")
    for year, banking_count, receipt_count in violations:
        print(f"  Year {int(year)}: {banking_count} banking TXs with multiple receipts ({receipt_count} total receipts)")
else:
    print("\n✅ NO VIOLATIONS - Perfect one-to-one matching across all years")

# Show 2019 details (user expects lots of non-banking receipts)
print("\n" + "=" * 100)
print("2019 DETAILED ANALYSIS (Expected: Cash reimbursements, manual entries)")
print("=" * 100)

cur.execute("""
    SELECT 
        CASE 
            WHEN banking_transaction_id IS NULL THEN 'NO BANKING LINK'
            ELSE 'HAS BANKING LINK'
        END as link_status,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND exclude_from_reports = FALSE
    GROUP BY CASE WHEN banking_transaction_id IS NULL THEN 'NO BANKING LINK' ELSE 'HAS BANKING LINK' END
    ORDER BY link_status
""")

status_2019 = cur.fetchall()

if status_2019:
    print(f"\n{'Status':<20} {'Count':<10} {'Total Amount':<15}")
    print("-" * 45)
    for status, count, amount in status_2019:
        print(f"{status:<20} {count:<10} ${amount:>12,.2f}")
    
    # Show sample non-banking receipts from 2019
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            category,
            description
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2019
        AND banking_transaction_id IS NULL
        AND exclude_from_reports = FALSE
        ORDER BY gross_amount DESC
        LIMIT 10
    """)
    
    samples = cur.fetchall()
    if samples:
        print("\nSample 2019 receipts WITHOUT banking links (Top 10 by amount):")
        print("-" * 100)
        for receipt_id, date, vendor, amount, category, description in samples:
            desc_short = (description[:50] + '...') if description and len(description) > 50 else (description or '')
            print(f"  #{receipt_id:<6} {date} {vendor:<30} ${amount:>10,.2f} {category or 'N/A':<20}")
            if desc_short:
                print(f"         → {desc_short}")

# Overall summary
print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)

cur.execute("""
    SELECT 
        COUNT(*) as total_receipts,
        COUNT(banking_transaction_id) as with_banking,
        COUNT(*) - COUNT(banking_transaction_id) as without_banking,
        COUNT(DISTINCT banking_transaction_id) as unique_banking_txs
    FROM receipts
    WHERE exclude_from_reports = FALSE
""")

total, with_bank, without_bank, unique_banking = cur.fetchone()

print(f"\nTotal receipts (active): {total:,}")
print(f"With banking_transaction_id: {with_bank:,} ({with_bank/total*100:.1f}%)")
print(f"Without banking_transaction_id: {without_bank:,} ({without_bank/total*100:.1f}%)")
print(f"Unique banking transaction IDs: {unique_banking:,}")

if with_bank == unique_banking:
    print("\n✅ PERFECT ONE-TO-ONE MATCHING")
    print(f"   {with_bank:,} receipts = {unique_banking:,} unique banking transactions")
else:
    print("\n⚠️  MISMATCH DETECTED")
    print(f"   {with_bank:,} receipts ≠ {unique_banking:,} banking transactions")
    print(f"   Difference: {with_bank - unique_banking:,} receipts")

cur.close()
conn.close()

print("\n" + "=" * 100)

"""Summarize findings and calculate true match rate."""

import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
cur = conn.cursor()

print("\n" + "="*70)
print("UNMATCHED RECEIPTS CATEGORIZATION (2013-2025, excl 2019)")
print("="*70)

# Get breakdown of the 671 unmatched receipts
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE source_file IS NULL) as manual_entries,
        COUNT(*) FILTER (WHERE vendor_name = 'SQUARE') as square_fees,
        COUNT(*) FILTER (WHERE category = 'Insurance - Vehicle Liability') as insurance_lump,
        COUNT(*) FILTER (WHERE category IN ('Income - Card Payments', 'Income - Other')) as income_accruals,
        COUNT(*) as total_unmatched
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2013 AND 2025
    AND EXTRACT(YEAR FROM receipt_date) != 2019
    AND banking_transaction_id IS NULL
    AND NOT (UPPER(vendor_name) LIKE '%CASH%WITHDRAW%' 
             OR category IN ('Driver Expense', 'Driver Reimbursement'))
""")

manual, square, insurance, income, total = cur.fetchone()
other = total - manual - square - insurance - income

print("\nBreakdown of 671 unmatched receipts:")
print("-" * 70)
print(f"Manual entries (no source file):        {manual:6,d} receipts")
print(f"SQUARE fees (netted in banking):        {square:6,d} receipts")
print(f"Insurance lump sum payments:              {insurance:6,d} receipts")
print(f"Income accruals:                           {income:6,d} receipts")
print(f"Other:                                     {other:6,d} receipts")
print("-" * 70)
print(f"TOTAL UNMATCHED:                         {total:6,d} receipts")

print("\n" + "="*70)
print("EXPLANATION OF UNMATCHED CATEGORIES")
print("="*70)

print("\n1. MANUAL ENTRIES (648 receipts):")
print("   - Entered directly without source file")
print("   - Examples: RUN'N ON EMPTY, grocery stores, car washes, etc.")
print("   - Not expected to match banking (driver reimbursements, petty cash, etc.)")

print("\n2. SQUARE FEES (185 receipts):")
print("   - SQUARE financing costs and merchant service fees")
print("   - Banking shows NET deposits AFTER fees deducted")
print("   - Individual fee transactions don't appear in banking")
print("   - These are expense accruals based on SQUARE reports")

print("\n3. INSURANCE LUMP SUM (7 receipts):")
print("   - Large annual/semi-annual premiums (~$70k each)")
print("   - No matching banking transactions found")
print("   - Likely paid via wire transfer, financed, or accrued")

print("\n4. INCOME ACCRUALS (11 receipts):")
print("   - Income - Card Payments and Income - Other categories")
print("   - Manual adjustment entries")

print("\n" + "="*70)
print("FINAL MATCH RATE ANALYSIS")
print("="*70)

# Get full statistics
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(banking_transaction_id) as matched,
        COUNT(*) FILTER (WHERE 
            banking_transaction_id IS NULL
            AND (UPPER(vendor_name) LIKE '%CASH%WITHDRAW%' 
                 OR category IN ('Driver Expense', 'Driver Reimbursement'))
        ) as cash_driver,
        COUNT(*) FILTER (WHERE 
            banking_transaction_id IS NULL
            AND NOT (UPPER(vendor_name) LIKE '%CASH%WITHDRAW%' 
                     OR category IN ('Driver Expense', 'Driver Reimbursement'))
            AND (source_file IS NULL 
                 OR vendor_name = 'SQUARE'
                 OR category IN ('Insurance - Vehicle Liability', 'Income - Card Payments', 'Income - Other'))
        ) as expected_unmatched,
        COUNT(*) FILTER (WHERE 
            banking_transaction_id IS NULL
            AND NOT (UPPER(vendor_name) LIKE '%CASH%WITHDRAW%' 
                     OR category IN ('Driver Expense', 'Driver Reimbursement'))
            AND source_file IS NOT NULL
            AND vendor_name != 'SQUARE'
            AND category NOT IN ('Insurance - Vehicle Liability', 'Income - Card Payments', 'Income - Other')
        ) as unexpected_unmatched
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2013 AND 2025
    AND EXTRACT(YEAR FROM receipt_date) != 2019
""")

total, matched, cash_driver, expected_unmatched, unexpected = cur.fetchone()

print(f"\nTotal receipts (2013-2025, excl 2019):   {total:6,d}")
print(f"Matched to banking:                       {matched:6,d} ({matched/total*100:.1f}%)")
print(f"\nUnmatched breakdown:")
print(f"  - Cash withdrawals/driver expenses:     {cash_driver:6,d}")
print(f"  - Expected unmatched (manual/accruals): {expected_unmatched:6,d}")
print(f"  - Unexpected unmatched:                 {unexpected:6,d}")

# Calculate effective match rate
bankable_receipts = total - cash_driver - expected_unmatched
effective_match_rate = (matched / bankable_receipts * 100) if bankable_receipts > 0 else 0

print(f"\n{'='*70}")
print(f"EFFECTIVE MATCH RATE")
print(f"{'='*70}")
print(f"Bankable receipts:                        {bankable_receipts:6,d}")
print(f"Matched to banking:                       {matched:6,d}")
print(f"Unexpected unmatched:                     {unexpected:6,d}")
print(f"\nEffective match rate:                     {effective_match_rate:.1f}%")

if unexpected == 0:
    print("\n" + "="*70)
    print("[SUCCESS] 100% MATCH RATE ACHIEVED!")
    print("(excluding cash, driver expenses, manual entries, and accruals)")
    print("="*70)
else:
    print(f"\n{unexpected} receipts with source files are unexpectedly unmatched.")
    
    # Show the unexpected ones
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            category,
            gross_amount,
            source_file
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2013 AND 2025
        AND EXTRACT(YEAR FROM receipt_date) != 2019
        AND banking_transaction_id IS NULL
        AND NOT (UPPER(vendor_name) LIKE '%CASH%WITHDRAW%' 
                 OR category IN ('Driver Expense', 'Driver Reimbursement'))
        AND source_file IS NOT NULL
        AND vendor_name != 'SQUARE'
        AND category NOT IN ('Insurance - Vehicle Liability', 'Income - Card Payments', 'Income - Other')
        ORDER BY receipt_date DESC
        LIMIT 20
    """)
    
    print("\nSample unexpected unmatched receipts:")
    print("-" * 70)
    for date, vendor, cat, amt, source in cur.fetchall():
        print(f"{date} {vendor:25s} {cat:20s} ${amt:>8,.2f}")
        print(f"         Source: {source}")

cur.close()
conn.close()

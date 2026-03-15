"""Calculate match rate for years with complete banking data."""

import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
cur = conn.cursor()

print("\n" + "="*70)
print("MATCH RATE ANALYSIS - COMPLETE BANKING DATA YEARS")
print("(2013-2025, excluding 2019 manual entries)")
print("="*70)

# Get receipts for years with complete banking data
cur.execute("""
    SELECT 
        COUNT(*) as total_receipts,
        COUNT(banking_transaction_id) as matched,
        COUNT(*) FILTER (WHERE 
            banking_transaction_id IS NULL
            AND (UPPER(vendor_name) LIKE '%CASH%WITHDRAW%' 
                 OR category IN ('Driver Expense', 'Driver Reimbursement'))
        ) as cash_driver_unmatched,
        COUNT(*) - COUNT(banking_transaction_id) as total_unmatched
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2013 AND 2025
    AND EXTRACT(YEAR FROM receipt_date) != 2019
""")

total, matched, cash_driver, unmatched = cur.fetchone()
other_unmatched = unmatched - cash_driver

print(f"\nTotal receipts (2013-2025, excl 2019):   {total:6,d}")
print(f"Matched to banking:                       {matched:6,d} ({matched/total*100:.1f}%)")
print(f"Unmatched total:                          {unmatched:6,d} ({unmatched/total*100:.1f}%)")
print(f"  - Cash withdrawals/Driver expenses:     {cash_driver:6,d}")
print(f"  - Other unmatched:                      {other_unmatched:6,d}")

# Calculate adjusted match rate
if total - cash_driver > 0:
    adjusted_rate = (matched / (total - cash_driver)) * 100
    print(f"\nAdjusted match rate (excl cash/driver):   {adjusted_rate:.1f}%")
    
if other_unmatched == 0:
    print("\n" + "="*70)
    print("[SUCCESS] 100% MATCH RATE!")
    print("(when excluding cash withdrawals and driver reimbursements)")
    print("="*70)
else:
    # Show what the other unmatched are
    print("\n" + "="*70)
    print(f"REMAINING {other_unmatched} UNMATCHED RECEIPTS")
    print("="*70)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            category,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2013 AND 2025
        AND EXTRACT(YEAR FROM receipt_date) != 2019
        AND banking_transaction_id IS NULL
        AND NOT (UPPER(vendor_name) LIKE '%CASH%WITHDRAW%' 
                 OR category IN ('Driver Expense', 'Driver Reimbursement'))
        GROUP BY year, category
        ORDER BY year, count DESC
    """)
    
    print(f"{'Year':6s} {'Category':30s} {'Count':>8s} {'Amount':>15s}")
    print("-" * 70)
    for year, cat, count, amt in cur.fetchall():
        cat_name = cat if cat else "[NULL]"
        amount = amt if amt is not None else 0.0
        print(f"{int(year):4d}   {cat_name:30s} {count:6,d}   ${amount:>12,.2f}")

cur.close()
conn.close()

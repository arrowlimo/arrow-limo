"""Comprehensive verification of CIBC 1615 data (2012-2017) - all years, all balances."""

import psycopg2
import os

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 110)
    print("CIBC ACCOUNT 1615 - COMPLETE VERIFICATION (2012-2017)")
    print("=" * 110)
    
    # 1. Transaction count by year
    print("\n1. TRANSACTION COUNT BY YEAR:")
    print("-" * 110)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date)::int as year,
            COUNT(*) as txn_count,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date
        FROM banking_transactions
        WHERE account_number = '1615'
        GROUP BY year
        ORDER BY year
    """)
    
    total_txns = 0
    for year, count, first_date, last_date in cur.fetchall():
        total_txns += count
        print(f"  {year}: {count:3d} transactions ({first_date} to {last_date})")
    
    print(f"\n  TOTAL: {total_txns} transactions")
    
    # 2. Opening and closing balances by year
    print("\n2. BALANCE VERIFICATION BY YEAR:")
    print("-" * 110)
    
    year_balances = {}
    for year in range(2012, 2018):
        # Get opening balance (first transaction of year)
        cur.execute("""
            SELECT balance FROM banking_transactions
            WHERE account_number = '1615'
            AND EXTRACT(YEAR FROM transaction_date) = %s
            ORDER BY transaction_date ASC
            LIMIT 1
        """, (year,))
        opening = cur.fetchone()
        
        # Get closing balance (last transaction of year)
        cur.execute("""
            SELECT balance FROM banking_transactions
            WHERE account_number = '1615'
            AND EXTRACT(YEAR FROM transaction_date) = %s
            ORDER BY transaction_date DESC
            LIMIT 1
        """, (year,))
        closing = cur.fetchone()
        
        opening_bal = opening[0] if opening and opening[0] is not None else None
        closing_bal = closing[0] if closing and closing[0] is not None else None
        
        year_balances[year] = (opening_bal, closing_bal)
        
        opening_str = f"${opening_bal:>12.2f}" if opening_bal is not None else "       N/A"
        closing_str = f"${closing_bal:>12.2f}" if closing_bal is not None else "       N/A"
        
        print(f"  {year}: Opening {opening_str} → Closing {closing_str}")
    
    # 3. Verify balance continuity year-to-year
    print("\n3. BALANCE CONTINUITY CHECK (Year-end to Year-start):")
    print("-" * 110)
    
    continuity_ok = True
    for year in range(2013, 2018):
        prev_closing = year_balances[year - 1][1]
        curr_opening = year_balances[year][0]
        
        if prev_closing is not None and curr_opening is not None:
            if abs(prev_closing - curr_opening) < 0.01:
                status = "✅ MATCH"
            else:
                status = f"❌ MISMATCH (diff: ${prev_closing - curr_opening:.2f})"
                continuity_ok = False
            print(f"  {year-1} closing ${prev_closing:>12.2f} → {year} opening ${curr_opening:>12.2f} : {status}")
        else:
            print(f"  {year-1} closing → {year} opening : DATA MISSING")
            continuity_ok = False
    
    # 4. Detail view of all transactions by year
    print("\n4. DETAILED TRANSACTION COUNT BY MONTH-YEAR:")
    print("-" * 110)
    
    cur.execute("""
        SELECT 
            DATE_TRUNC('month', transaction_date)::date as month,
            COUNT(*) as count,
            MIN(balance) as min_balance,
            MAX(balance) as max_balance
        FROM banking_transactions
        WHERE account_number = '1615'
        GROUP BY month
        ORDER BY month
    """)
    
    for month, count, min_bal, max_bal in cur.fetchall():
        if min_bal is not None and max_bal is not None:
            print(f"  {month}: {count:2d} txns | Range: ${min_bal:>12.2f} to ${max_bal:>12.2f}")
        else:
            print(f"  {month}: {count:2d} txns | Range: N/A")
    
    # 5. Summary statistics
    print("\n5. DATA COMPLETENESS SUMMARY:")
    print("-" * 110)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT EXTRACT(YEAR FROM transaction_date)) as years_covered,
            COUNT(DISTINCT DATE_TRUNC('month', transaction_date)) as months_covered,
            MIN(transaction_date) as earliest_date,
            MAX(transaction_date) as latest_date,
            COUNT(CASE WHEN balance IS NULL THEN 1 END) as null_balances
        FROM banking_transactions
        WHERE account_number = '1615'
    """)
    
    stats = cur.fetchone()
    total_recs, years, months, earliest, latest, nulls = stats
    
    print(f"  Total Records:        {total_recs}")
    print(f"  Years Covered:        {int(years)} years (2012-2017)")
    print(f"  Months Covered:       {int(months)} months")
    print(f"  Date Range:           {earliest} to {latest}")
    print(f"  NULL Balance Values:  {nulls}")
    
    # 6. Final verdict
    print("\n6. VERIFICATION VERDICT:")
    print("-" * 110)
    
    expected_months = 12 * 6  # 6 years × 12 months = 72
    
    all_ok = True
    
    if total_txns > 0:
        print("  ✅ Data exists in database")
    else:
        print("  ❌ NO DATA in database")
        all_ok = False
    
    if int(years) == 6:
        print("  ✅ All 6 years (2012-2017) present")
    else:
        print(f"  ❌ Only {int(years)} years present (expected 6)")
        all_ok = False
    
    if int(months) >= expected_months - 2:  # Allow 2 missing months
        print(f"  ✅ {int(months)} months covered (expected ~{expected_months})")
    else:
        print(f"  ❌ Only {int(months)} months covered (expected ~{expected_months})")
        all_ok = False
    
    if nulls == 0:
        print("  ✅ All balance values populated (NO nulls)")
    else:
        print(f"  ⚠️  {nulls} NULL balance values found")
    
    if continuity_ok:
        print("  ✅ Balance continuity verified (year-end → year-start)")
    else:
        print("  ❌ Balance continuity issues detected")
        all_ok = False
    
    print("\n" + "=" * 110)
    if all_ok:
        print("FINAL RESULT: ✅ ALL DATA VERIFIED - 2012-2017 COMPLETE AND BALANCED")
    else:
        print("FINAL RESULT: ⚠️  PARTIAL DATA - ISSUES DETECTED (see above)")
    print("=" * 110)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

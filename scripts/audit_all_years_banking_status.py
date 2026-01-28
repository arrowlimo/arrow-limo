"""
Check banking data status for all years (2007-2025).
Shows which years have transactions, balances, and identifies gaps.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 100)
    print("BANKING DATA STATUS BY YEAR (2007-2025)")
    print("=" * 100)
    
    # Get yearly summary
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            COUNT(*) as transaction_count,
            COUNT(DISTINCT account_number) as account_count,
            COUNT(CASE WHEN balance IS NOT NULL THEN 1 END) as transactions_with_balance,
            COUNT(CASE WHEN balance IS NULL THEN 1 END) as transactions_missing_balance,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) >= 2007
        GROUP BY EXTRACT(YEAR FROM transaction_date)
        ORDER BY year
    """)
    
    results = cur.fetchall()
    
    if not results:
        print("\n⚠️  No banking transactions found for 2007-2025")
        cur.close()
        conn.close()
        return
    
    print("\n" + "=" * 100)
    print(f"{'Year':<6} {'Txns':<7} {'Accounts':<9} {'With Bal':<10} {'Missing Bal':<12} {'Status':<20}")
    print("=" * 100)
    
    years_complete = []
    years_missing_balances = []
    years_no_data = []
    
    # Check all years from 2007 to 2025
    for year in range(2007, 2026):
        year_data = next((r for r in results if int(r['year']) == year), None)
        
        if year_data:
            txn_count = year_data['transaction_count']
            acc_count = year_data['account_count']
            with_bal = year_data['transactions_with_balance']
            missing_bal = year_data['transactions_missing_balance']
            
            # Determine status
            if missing_bal == 0:
                status = "✅ COMPLETE"
                years_complete.append(year)
            elif with_bal == 0:
                status = "⚠️  NO BALANCES"
                years_missing_balances.append(year)
            else:
                pct = (with_bal / txn_count * 100)
                status = f"⚠️  {pct:.0f}% PARTIAL"
                years_missing_balances.append(year)
            
            print(f"{year:<6} {txn_count:<7} {acc_count:<9} {with_bal:<10} {missing_bal:<12} {status:<20}")
        else:
            years_no_data.append(year)
            print(f"{year:<6} {'0':<7} {'0':<9} {'0':<10} {'0':<12} {'❌ NO DATA':<20}")
    
    # Monthly breakdown for years with data
    print("\n" + "=" * 100)
    print("MONTHLY COVERAGE BY YEAR")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            EXTRACT(MONTH FROM transaction_date) as month,
            COUNT(*) as count
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) >= 2007
        GROUP BY EXTRACT(YEAR FROM transaction_date), EXTRACT(MONTH FROM transaction_date)
        ORDER BY year, month
    """)
    
    monthly_data = cur.fetchall()
    
    # Group by year
    year_months = {}
    for row in monthly_data:
        year = int(row['year'])
        month = int(row['month'])
        if year not in year_months:
            year_months[year] = set()
        year_months[year].add(month)
    
    for year in range(2007, 2026):
        if year in year_months:
            months = year_months[year]
            missing = set(range(1, 13)) - months
            
            month_str = ''.join(['✓' if m in months else '✗' for m in range(1, 13)])
            
            if missing:
                print(f"{year}: {month_str}  ⚠️  Missing: {sorted(missing)}")
            else:
                print(f"{year}: {month_str}  ✅ Complete")
        else:
            print(f"{year}: ✗✗✗✗✗✗✗✗✗✗✗✗  ❌ No data")
    
    # Summary
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    
    print(f"\n✅ YEARS WITH COMPLETE BALANCE DATA: {len(years_complete)}")
    if years_complete:
        print(f"   {', '.join(map(str, years_complete))}")
    
    print(f"\n⚠️  YEARS WITH MISSING BALANCES: {len(years_missing_balances)}")
    if years_missing_balances:
        print(f"   {', '.join(map(str, years_missing_balances))}")
        print("\n   ACTION REQUIRED: Scan paper statements and extract balance data")
    
    print(f"\n❌ YEARS WITH NO DATA: {len(years_no_data)}")
    if years_no_data:
        print(f"   {', '.join(map(str, years_no_data))}")
        print("\n   ACTION REQUIRED: Import transaction data from statements")
    
    # Check for credit card data
    print("\n" + "=" * 100)
    print("CREDIT CARD DATA STATUS")
    print("=" * 100)
    
    try:
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM transaction_date) as year,
                COUNT(*) as count,
                SUM(amount) as total
            FROM cibc_card_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) >= 2007
            GROUP BY EXTRACT(YEAR FROM transaction_date)
            ORDER BY year
        """)
        cc_data = cur.fetchall()
        
        if cc_data:
            print("\n✅ CIBC Credit Card Data Found:")
            for row in cc_data:
                print(f"   {int(row['year'])}: {row['count']} transactions, ${row['total']:,.2f}")
        else:
            print("\n⚠️  No CIBC credit card data in database")
    except:
        print("\n⚠️  No cibc_card_transactions table")
    
    # Check Triangle Mastercard from receipts (2018+)
    print("\n📊 Triangle Mastercard statements available in PDFs: 2018-2025")
    print("   (Located in l:\\limo\\pdf\\triangle mastercard\\)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

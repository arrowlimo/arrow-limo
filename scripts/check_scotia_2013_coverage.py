"""
Check Scotia Bank 2013 database coverage by month.
Shows which months are imported and which need screenshot extraction.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get monthly breakdown for Scotia 2013
    cur.execute("""
        SELECT 
            DATE_TRUNC('month', transaction_date)::date as month,
            COUNT(*) as count,
            SUM(debit_amount) as debits,
            SUM(credit_amount) as credits
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2013
        GROUP BY DATE_TRUNC('month', transaction_date)
        ORDER BY month
    """)
    
    print("\n" + "="*80)
    print("Scotia Bank 2013 Current Database Coverage")
    print("="*80)
    
    months = cur.fetchall()
    if not months:
        print("\nNO DATA FOUND - All months need to be imported from screenshots")
    else:
        print(f"\n{'Month':<12} {'Transactions':>12} {'Debits':>15} {'Credits':>15}")
        print("-"*80)
        for row in months:
            month_str = row[0].strftime('%Y-%m')
            count = row[1]
            debits = row[2] or 0
            credits = row[3] or 0
            print(f"{month_str:<12} {count:>12,} ${debits:>14,.2f} ${credits:>14,.2f}")
    
    # Check total for year
    cur.execute("""
        SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2013
    """)
    total_count, total_debits, total_credits = cur.fetchone()
    
    print("-"*80)
    print(f"{'2013 TOTAL':<12} {total_count:>12,} ${total_debits or 0:>14,.2f} ${total_credits or 0:>14,.2f}")
    print("="*80)
    
    # List months that need to be imported
    all_months = [
        '2013-01', '2013-02', '2013-03', '2013-04', '2013-05', '2013-06',
        '2013-07', '2013-08', '2013-09', '2013-10', '2013-11', '2013-12'
    ]
    
    imported_months = [row[0].strftime('%Y-%m') for row in months]
    missing_months = [m for m in all_months if m not in imported_months]
    
    if missing_months:
        print("\nMONTHS NEEDING SCREENSHOT IMPORT:")
        for month in missing_months:
            print(f"  - {month}")
    else:
        print("\nALL MONTHS HAVE DATA (but may need verification)")
    
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

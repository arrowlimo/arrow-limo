"""
Analyze banking transaction date coverage and completeness

Shows:
- Overall date range
- Year-by-year breakdown
- Pre-2019 vs post-2019 coverage
- Gap analysis
"""
import psycopg2

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

def conn():
    return psycopg2.connect(**DB)

def main():
    cn = conn()
    try:
        cur = cn.cursor()
        
        # Overall summary
        cur.execute("""
            SELECT 
                MIN(transaction_date) as earliest, 
                MAX(transaction_date) as latest, 
                COUNT(*) as total,
                COUNT(DISTINCT EXTRACT(YEAR FROM transaction_date)) as years
            FROM banking_transactions
        """)
        row = cur.fetchone()
        
        print("\n" + "="*80)
        print("BANKING TRANSACTIONS OVERALL COVERAGE")
        print("="*80)
        print(f"  Earliest transaction: {row[0]}")
        print(f"  Latest transaction:   {row[1]}")
        print(f"  Total records:        {row[2]:,}")
        print(f"  Years covered:        {int(row[3])}")
        
        # Year-by-year breakdown
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM transaction_date)::INTEGER as year,
                COUNT(*) as records,
                MIN(transaction_date) as first_date,
                MAX(transaction_date) as last_date,
                SUM(CASE WHEN debit_amount IS NOT NULL THEN debit_amount ELSE 0 END) as total_debits,
                SUM(CASE WHEN credit_amount IS NOT NULL THEN credit_amount ELSE 0 END) as total_credits
            FROM banking_transactions
            GROUP BY EXTRACT(YEAR FROM transaction_date)
            ORDER BY year
        """)
        
        print("\n" + "="*120)
        print("YEAR-BY-YEAR BREAKDOWN")
        print("="*120)
        print(f"{'Year':<8} {'Records':<12} {'First Date':<15} {'Last Date':<15} {'Total Debits':<18} {'Total Credits':<18}")
        print("-"*120)
        
        pre_2019_records = 0
        pre_2019_debits = 0
        pre_2019_credits = 0
        post_2019_records = 0
        post_2019_debits = 0
        post_2019_credits = 0
        
        for row in cur.fetchall():
            year, records, first, last, debits, credits = row
            print(f"{year:<8} {records:<12,} {str(first):<15} {str(last):<15} ${debits or 0:<16,.2f} ${credits or 0:<16,.2f}")
            
            if year < 2019:
                pre_2019_records += records
                pre_2019_debits += (debits or 0)
                pre_2019_credits += (credits or 0)
            else:
                post_2019_records += records
                post_2019_debits += (debits or 0)
                post_2019_credits += (credits or 0)
        
        print("-"*120)
        
        # Pre-2019 vs Post-2019 summary
        print("\n" + "="*80)
        print("PRE-2019 vs POST-2019 COMPARISON")
        print("="*80)
        print(f"\nPRE-2019 (Before January 1, 2019):")
        print(f"  Records:       {pre_2019_records:,}")
        print(f"  Total Debits:  ${pre_2019_debits:,.2f}")
        print(f"  Total Credits: ${pre_2019_credits:,.2f}")
        print(f"  Status:        {'COMPLETE' if pre_2019_records > 0 else 'NO DATA'}")
        
        print(f"\nPOST-2019 (January 1, 2019 onwards):")
        print(f"  Records:       {post_2019_records:,}")
        print(f"  Total Debits:  ${post_2019_debits:,.2f}")
        print(f"  Total Credits: ${post_2019_credits:,.2f}")
        
        # Gap analysis
        cur.execute("""
            WITH date_series AS (
                SELECT generate_series(
                    (SELECT MIN(transaction_date) FROM banking_transactions),
                    (SELECT MAX(transaction_date) FROM banking_transactions),
                    '1 day'::interval
                )::date as dt
            ),
            transaction_dates AS (
                SELECT DISTINCT transaction_date FROM banking_transactions
            )
            SELECT COUNT(*) as gap_days
            FROM date_series ds
            LEFT JOIN transaction_dates td ON ds.dt = td.transaction_date
            WHERE td.transaction_date IS NULL
        """)
        gap_days = cur.fetchone()[0]
        
        print(f"\nGAP ANALYSIS:")
        print(f"  Days with no transactions: {gap_days:,}")
        
        # Check for specific pre-2019 data sources
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM transaction_date)::INTEGER as year,
                COUNT(DISTINCT account_number) as accounts,
                array_agg(DISTINCT LEFT(description, 30)) FILTER (WHERE description IS NOT NULL) as sample_descriptions
            FROM banking_transactions
            WHERE transaction_date < '2019-01-01'
            GROUP BY EXTRACT(YEAR FROM transaction_date)
            ORDER BY year
        """)
        
        print("\n" + "="*80)
        print("PRE-2019 DATA QUALITY")
        print("="*80)
        results = cur.fetchall()
        if results:
            for year, accounts, samples in results:
                print(f"\n{year}:")
                print(f"  Accounts: {accounts}")
                if samples:
                    print(f"  Sample transactions: {', '.join(samples[:5])}")
        else:
            print("\nNO PRE-2019 BANKING DATA FOUND")
        
        print("\n" + "="*80)
        
    finally:
        cn.close()

if __name__ == '__main__':
    main()

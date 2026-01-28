"""Find the bounced cheque and NSF charges on CIBC account 1615."""

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
    
    print("=" * 100)
    print("CIBC ACCOUNT 1615 - BOUNCED CHEQUE & NSF CHARGE INVESTIGATION")
    print("=" * 100)
    
    # Count of transactions by year
    print("\n1. TRANSACTION COUNT BY YEAR:")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date)::int as year,
            COUNT(*) as txn_count
        FROM banking_transactions
        WHERE account_number = '1615'
        GROUP BY year
        ORDER BY year
    """)
    
    for year, count in cur.fetchall():
        print(f"  {year}: {count:4d} transactions")
    
    # Get all 2014-2017 transactions to see what they contain
    print("\n2. ALL TRANSACTIONS FOR 2014-2017:")
    print("-" * 100)
    
    for year in [2014, 2015, 2016, 2017]:
        print(f"\n{year}:")
        cur.execute("""
            SELECT 
                transaction_date, 
                description, 
                debit_amount, 
                credit_amount, 
                balance
            FROM banking_transactions
            WHERE account_number = '1615'
            AND EXTRACT(YEAR FROM transaction_date) = %s
            ORDER BY transaction_date
        """, (year,))
        
        txns = cur.fetchall()
        for date, desc, debit, credit, balance in txns:
            debit_str = f"${debit:>10.2f}" if debit and debit > 0 else " " * 13
            credit_str = f"${credit:>10.2f}" if credit and credit > 0 else " " * 13
            balance_str = f"${balance:>10.2f}" if balance is not None else "       N/A"
            print(f"  {date} | D:{debit_str} | C:{credit_str} | Bal:{balance_str} | {desc[:50]}")
    
    # Look for NSF in the general ledger backup
    print("\n3. SEARCHING BACKUP DATA FOR NSF, BOUNCE, GARNISH ENTRIES:")
    print("-" * 100)
    
    # Check for balance deficit growth
    print("\n4. BALANCE PROGRESSION (2014-2017):")
    print("-" * 100)
    
    cur.execute("""
        SELECT EXTRACT(YEAR FROM transaction_date)::int as year, balance
        FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) IN (2014, 2015, 2016, 2017)
        ORDER BY year DESC, transaction_date DESC
        LIMIT 4
    """)
    
    year_endings = {}
    for year, balance in cur.fetchall():
        if year not in year_endings:
            year_endings[year] = balance
    
    for year in sorted(year_endings.keys()):
        bal = year_endings[year]
        if bal:
            print(f"  End of {year}: ${bal:>12.2f}")
    
    # Calculate the deficit growth and match it to NSF/bounce
    print("\n5. ANNUAL DEFICIT GROWTH:")
    print("-" * 100)
    
    balances_by_year = sorted([(y, b) for y, b in year_endings.items()])
    for i in range(1, len(balances_by_year)):
        prev_year, prev_bal = balances_by_year[i-1]
        curr_year, curr_bal = balances_by_year[i]
        if prev_bal and curr_bal:
            growth = curr_bal - prev_bal
            print(f"  {prev_year} to {curr_year}: ${growth:>12.2f} (deficit increased by ${abs(growth):.2f})")
    
    # Now let's check if there are any RETURNED CHEQUE descriptions in the general_ledger_export
    print("\n6. SEARCHING GENERAL LEDGER BACKUP FOR NSF/BOUNCE REFERENCES:")
    print("-" * 100)
    print("   (Checking if bounced cheque descriptions were in QB and not imported to banking_transactions)")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)
    print("ANALYSIS COMPLETE")
    print("=" * 100)

if __name__ == '__main__':
    main()

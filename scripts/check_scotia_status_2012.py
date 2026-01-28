"""
Check Scotia Bank 2012 import status for account 903990106011.
"""
import psycopg2
import os

# Set environment variables
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_NAME'] = 'almsdata'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = '***REMOVED***'

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("SCOTIA BANK 2012 STATUS CHECK")
    print("=" * 80)
    print()
    
    # Check overall Scotia 2012 status
    cur.execute("""
        SELECT 
            COUNT(*),
            MIN(transaction_date),
            MAX(transaction_date),
            COALESCE(SUM(debit_amount), 0),
            COALESCE(SUM(credit_amount), 0)
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    row = cur.fetchone()
    
    print(f"Scotia Bank Account 903990106011 - 2012:")
    print(f"  Transactions: {row[0]}")
    print(f"  Date Range: {row[1]} to {row[2]}")
    print(f"  Total Debits: ${row[3]:,.2f}")
    print(f"  Total Credits: ${row[4]:,.2f}")
    print()
    
    # Check monthly breakdown
    print("Monthly Breakdown:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            TO_CHAR(transaction_date, 'YYYY-MM') as month,
            COUNT(*) as txn_count,
            COALESCE(SUM(debit_amount), 0) as debits,
            COALESCE(SUM(credit_amount), 0) as credits
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        GROUP BY TO_CHAR(transaction_date, 'YYYY-MM')
        ORDER BY month
    """)
    
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]:4d} transactions, ${row[2]:10,.2f} debits, ${row[3]:10,.2f} credits")
    
    print()
    
    # Check receipts created from Scotia banking
    cur.execute("""
        SELECT 
            COUNT(*),
            COALESCE(SUM(gross_amount), 0)
        FROM receipts
        WHERE mapped_bank_account_id = 2
        AND created_from_banking = TRUE
        AND EXTRACT(YEAR FROM receipt_date) = 2012
    """)
    row = cur.fetchone()
    
    print(f"Receipts Created from Scotia Banking (2012):")
    print(f"  Count: {row[0]}")
    print(f"  Total Amount: ${row[1]:,.2f}")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

"""
Check for 2013 banking and credit card data in database.
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
    
    print("=" * 80)
    print("CHECKING DATABASE FOR 2013 BANKING AND CREDIT CARD DATA")
    print("=" * 80)
    
    # Find banking/card related tables
    print("\n1. BANKING/CARD TABLES IN DATABASE:")
    print("-" * 80)
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND (table_name LIKE '%bank%' OR table_name LIKE '%card%')
        ORDER BY table_name
    """)
    tables = cur.fetchall()
    
    if tables:
        for t in tables:
            print(f"  - {t['table_name']}")
    else:
        print("  No banking/card tables found")
    
    # Check banking_transactions table for 2013 data
    print("\n2. BANKING_TRANSACTIONS TABLE - 2013 DATA:")
    print("-" * 80)
    try:
        cur.execute("""
            SELECT 
                account_number,
                COUNT(*) as transaction_count,
                MIN(transaction_date) as first_date,
                MAX(transaction_date) as last_date,
                SUM(debit_amount) as total_debits,
                SUM(credit_amount) as total_credits
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = 2013
            GROUP BY account_number
            ORDER BY account_number
        """)
        results = cur.fetchall()
        
        if results:
            for row in results:
                print(f"\nAccount: {row['account_number']}")
                print(f"  Transactions: {row['transaction_count']}")
                print(f"  Date Range: {row['first_date']} to {row['last_date']}")
                print(f"  Total Debits: ${row['total_debits']:,.2f}")
                print(f"  Total Credits: ${row['total_credits']:,.2f}")
        else:
            print("  No 2013 transactions found in banking_transactions table")
    except Exception as e:
        print(f"  Error querying banking_transactions: {e}")
    
    # Check for credit card tables
    print("\n3. CREDIT CARD TABLES - 2013 DATA:")
    print("-" * 80)
    
    # Check common credit card table names
    card_tables = ['credit_card_transactions', 'mastercard_transactions', 
                   'triangle_mastercard', 'receipts', 'merchant_statements']
    
    for table_name in card_tables:
        try:
            cur.execute(f"""
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_name = '{table_name}'
            """)
            exists = cur.fetchone()['count']
            
            if exists:
                cur.execute(f"""
                    SELECT COUNT(*) as count
                    FROM {table_name}
                    WHERE EXTRACT(YEAR FROM 
                        CASE 
                            WHEN EXISTS (SELECT 1 FROM information_schema.columns 
                                        WHERE table_name = '{table_name}' 
                                        AND column_name = 'transaction_date')
                            THEN transaction_date
                            WHEN EXISTS (SELECT 1 FROM information_schema.columns 
                                        WHERE table_name = '{table_name}' 
                                        AND column_name = 'receipt_date')
                            THEN receipt_date
                            ELSE NULL
                        END
                    ) = 2013
                """)
                count = cur.fetchone()['count']
                if count > 0:
                    print(f"  {table_name}: {count} records for 2013")
        except Exception as e:
            continue
    
    # Check receipts table specifically for credit card expenses
    print("\n4. RECEIPTS TABLE - 2013 CREDIT CARD EXPENSES:")
    print("-" * 80)
    try:
        cur.execute("""
            SELECT 
                COUNT(*) as count,
                SUM(COALESCE(gross_amount, 0)) as total
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2013
            AND (description LIKE '%card%' OR vendor_name LIKE '%mastercard%' 
                 OR vendor_name LIKE '%triangle%')
        """)
        result = cur.fetchone()
        
        if result['count'] > 0:
            print(f"  Credit card receipts: {result['count']} receipts, ${result['total']:,.2f}")
        else:
            print("  No credit card related receipts found for 2013")
    except Exception as e:
        print(f"  Error: {e}")
        conn.rollback()  # Rollback failed transaction
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    
    # Check if ANY 2013 financial data exists
    try:
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM banking_transactions 
                 WHERE EXTRACT(YEAR FROM transaction_date) = 2013) as banking_count,
                (SELECT COUNT(*) FROM receipts 
                 WHERE EXTRACT(YEAR FROM receipt_date) = 2013) as receipts_count,
                (SELECT COUNT(*) FROM payments 
                 WHERE EXTRACT(YEAR FROM payment_date) = 2013) as payments_count,
                (SELECT COUNT(*) FROM charters 
                 WHERE EXTRACT(YEAR FROM charter_date) = 2013) as charters_count
        """)
        summary = cur.fetchone()
        
        print(f"2013 Banking Transactions: {summary['banking_count']}")
        print(f"2013 Receipts: {summary['receipts_count']}")
        print(f"2013 Payments: {summary['payments_count']}")
        print(f"2013 Charters: {summary['charters_count']}")
        
        if summary['banking_count'] == 0:
            print("\n⚠️  WARNING: No 2013 banking transactions in database")
            print("   PDF statements need to be located and imported")
    except Exception as e:
        print(f"Error: {e}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

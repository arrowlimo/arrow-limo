import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check for account 1615 data
cur.execute("""
    SELECT 
        COUNT(*) as total_count,
        MIN(transaction_date) as earliest_date,
        MAX(transaction_date) as latest_date,
        SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debits,
        SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_credits,
        MIN(balance) as min_balance,
        MAX(balance) as max_balance
    FROM banking_transactions
    WHERE account_number = '1615'
""")

result = cur.fetchone()
if result[0] > 0:
    print(f"CIBC Account 1615 current data:")
    print(f"  Total transactions: {result[0]}")
    print(f"  Date range: {result[1]} to {result[2]}")
    print(f"  Total debits: ${result[3]:.2f}" if result[3] else "  Total debits: $0.00")
    print(f"  Total credits: ${result[4]:.2f}" if result[4] else "  Total credits: $0.00")
    print(f"  Balance range: ${result[5]:.2f} to ${result[6]:.2f}" if result[5] else "  Balance range: Unknown")
    
    # Show monthly breakdown
    print(f"\nMonthly breakdown:")
    cur.execute("""
        SELECT 
            DATE_TRUNC('month', transaction_date)::DATE as month,
            COUNT(*) as count,
            SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as debits,
            SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as credits
        FROM banking_transactions
        WHERE account_number = '1615'
        GROUP BY DATE_TRUNC('month', transaction_date)
        ORDER BY month
    """)
    
    for row in cur.fetchall():
        month, count, debits, credits = row
        print(f"  {month.strftime('%Y-%m')}: {count} txns, D:${debits or 0:.2f}, C:${credits or 0:.2f}")
else:
    print("No data found for account 1615")
    print("\nChecking what CIBC accounts exist in database:")
    cur.execute("""
        SELECT DISTINCT account_number, COUNT(*) as count
        FROM banking_transactions
        WHERE account_number LIKE '%1615%' OR account_number LIKE '%-1615%'
        GROUP BY account_number
    """)
    
    results = cur.fetchall()
    if results:
        for acct, count in results:
            print(f"  {acct}: {count} transactions")
    else:
        print("  No account matching '1615' found")
        
        # Show all CIBC accounts
        cur.execute("""
            SELECT DISTINCT account_number, COUNT(*) as count
            FROM banking_transactions
            GROUP BY account_number
            ORDER BY account_number
        """)
        
        print("\nAll banking accounts in database:")
        for acct, count in cur.fetchall():
            print(f"  {acct}: {count} transactions")

cur.close()
conn.close()

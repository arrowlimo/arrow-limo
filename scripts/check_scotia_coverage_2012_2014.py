"""Check Scotia Bank data coverage for 2012-2014 period."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check Scotia Bank data by year
for year in [2012, 2013, 2014]:
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest,
            ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2) as debits,
            ROUND(SUM(COALESCE(credit_amount, 0))::numeric, 2) as credits
        FROM banking_transactions
        WHERE account_number = '3714081'
        AND EXTRACT(YEAR FROM transaction_date) = %s
    """, (year,))
    
    result = cur.fetchone()
    print(f"\nScotia Bank {year}:")
    if result[0] > 0:
        print(f"  Transactions: {result[0]}")
        print(f"  Date Range: {result[1]} to {result[2]}")
        print(f"  Total Debits: ${result[3]:,.2f}")
        print(f"  Total Credits: ${result[4]:,.2f}")
    else:
        print(f"  NO DATA")

# Check by month for 2012
print(f"\n\nScotia Bank 2012 Monthly Breakdown:")
cur.execute("""
    SELECT 
        TO_CHAR(transaction_date, 'YYYY-MM') as month,
        COUNT(*) as transactions,
        ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2) as debits,
        ROUND(SUM(COALESCE(credit_amount, 0))::numeric, 2) as credits
    FROM banking_transactions
    WHERE account_number = '3714081'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY TO_CHAR(transaction_date, 'YYYY-MM')
    ORDER BY month
""")

for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} txns, Debits: ${row[2]:,.2f}, Credits: ${row[3]:,.2f}")

if cur.rowcount == 0:
    print("  No monthly data found")

cur.close()
conn.close()

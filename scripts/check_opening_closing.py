"""Check if we have explicit opening/closing balance marker entries."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

for year in [2012, 2013, 2014, 2015, 2016, 2017]:
    print(f"\n{year}:")
    print("-" * 80)
    
    cur.execute("""
        SELECT transaction_date, description, balance 
        FROM banking_transactions 
        WHERE account_number = '1615' 
        AND EXTRACT(YEAR FROM transaction_date) = %s
        AND description IN ('Opening balance', 'Closing balance')
        ORDER BY transaction_date ASC
    """, (year,))
    
    rows = cur.fetchall()
    if rows:
        for row in rows:
            print(f"  {row[0]} | {row[1]} | ${row[2]}")
    else:
        print("  No Opening/Closing marker entries")

conn.close()

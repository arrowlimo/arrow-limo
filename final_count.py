import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("="*80)
print("FINAL SCOTIA 2013-2014 COUNT")
print("="*80)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as count,
        SUM(debit_amount) as debits,
        SUM(credit_amount) as credits
    FROM banking_transactions
    WHERE account_number = '903990106011'
      AND EXTRACT(YEAR FROM transaction_date) IN (2013, 2014)
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year
""")

for row in cur.fetchall():
    print(f"\n{int(row[0])}: {row[1]} transactions")
    print(f"  Debits: ${float(row[2]):,.2f}")
    print(f"  Credits: ${float(row[3]):,.2f}")

cur.execute("""
    SELECT COUNT(*) FROM banking_transactions
    WHERE account_number = '903990106011'
      AND EXTRACT(YEAR FROM transaction_date) IN (2013, 2014)
""")
total = cur.fetchone()[0]
print(f"\n{'='*80}")
print(f"TOTAL: {total} transactions")
print(f"Expected: 2627")
print(f"Missing: {2627 - total}")
print(f"{'='*80}")

cur.close()
conn.close()

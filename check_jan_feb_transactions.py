import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("JANUARY + FEBRUARY 2012 TRANSACTIONS IN DATABASE:\n")
print(f"{'Date':<12} | {'Description':<40} | {'Debit':>8} | {'Credit':>8} | {'Balance':>10}")
print("-" * 90)

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance 
    FROM banking_transactions 
    WHERE account_number='1615' 
    AND transaction_date BETWEEN '2012-01-01' AND '2012-02-29' 
    ORDER BY transaction_date, created_at
""")

rows = cur.fetchall()
for row in rows:
    date_str = str(row[0])
    desc = row[1][:40] if row[1] else ""
    debit = f"{row[2]:.2f}" if row[2] else ""
    credit = f"{row[3]:.2f}" if row[3] else ""
    balance = row[4]
    print(f"{date_str} | {desc:<40} | {debit:>8} | {credit:>8} | {balance:>10.2f}")

print(f"\nTotal Jan-Feb records: {len(rows)}")

# Check what we expect
print("\n" + "=" * 90)
print("EXPECTED BALANCES:")
print("Jan 1: $7,177.34 (opening)")
print("Jan 31: -$49.17 (closing)")
print("Feb 1: -$49.17 (opening - should match Jan 31)")
print("Feb 29: $1,014.49 (closing)")

cur.close()
conn.close()

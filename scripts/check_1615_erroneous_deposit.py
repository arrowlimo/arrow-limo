"""Check if erroneous $35,244.36 deposit exists and find the correct 2012 starting balance."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("1. Checking for erroneous $35,244.36 deposit:")
print("=" * 80)

cur.execute("""
    SELECT transaction_date, description, credit_amount, debit_amount, balance
    FROM banking_transactions
    WHERE account_number = '1615'
    AND (credit_amount = 35244.36 OR credit_amount = 35211.03)
""")

result = cur.fetchall()
print(f"Found {len(result)} matching transactions with that exact amount")
if result:
    for date, desc, credit, debit, bal in result:
        print(f"  {date} | {desc} | Credit: ${credit:.2f} | Balance: ${bal:.2f if bal else 0}")
else:
    print("  ✅ Erroneous deposit NOT found (good - already removed)")

print("\n2. Checking for ANY 2012 data:")
print("=" * 80)

cur.execute("""
    SELECT COUNT(*) FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")

count_2012 = cur.fetchone()[0]
print(f"2012 transactions in database: {count_2012}")

if count_2012 == 0:
    print("  ❌ No 2012 data - needs to be imported")

print("\n3. What should the 2012 ending balance be (to link to 2013)?")
print("=" * 80)

# Get first 2013 transaction to see what 2012 should end at
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2013
    ORDER BY transaction_date ASC
    LIMIT 1
""")

first_2013 = cur.fetchone()
if first_2013:
    print(f"First 2013 transaction: {first_2013[0]} | Balance: {first_2013[2] if first_2013[2] else 'NULL'}")
    if first_2013[2] is None:
        print("  ⚠️  2013 has NULL balances - we need to calculate them")
    else:
        print(f"  → 2012 should END at: ${first_2013[2]:.2f}")

cur.close()
conn.close()

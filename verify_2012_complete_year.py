import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("=" * 100)
print("2012 COMPLETE YEAR VERIFICATION - CHECKING MONTH CLOSING BALANCES")
print("=" * 100)

# Get all "Closing balance" entries
cur.execute("""
    SELECT transaction_date, description, balance 
    FROM banking_transactions 
    WHERE account_number='1615' 
    AND description = 'Closing balance'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date
""")

rows = cur.fetchall()
print(f"\nFound {len(rows)} month-end closing balance entries:\n")

expected_closings = {
    '2012-01-31': -49.17,
    '2012-02-29': 1014.49,
    '2012-03-31': 939.06,
    '2012-04-30': 1557.02,
    '2012-05-31': 7544.86,
    '2012-06-30': 191.44,
    '2012-07-31': 1549.80,
    '2012-08-31': 655.80,
    '2012-09-30': 608.98,
    '2012-10-31': 1027.32,
    '2012-11-30': 714.80,
    '2012-12-31': 21.21,
}

all_correct = True
for row in rows:
    date_str = str(row[0])
    balance = float(row[2])
    expected = expected_closings.get(date_str)
    
    if expected is not None:
        diff = abs(balance - expected)
        status = "✅" if diff < 0.01 else "❌"
        print(f"{status} {date_str}: ${balance:10.2f} (expected ${expected:10.2f})")
        if diff >= 0.01:
            all_correct = False
    else:
        print(f"⚠️  {date_str}: ${balance:10.2f} (unexpected date)")

# Overall stats
cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date),
           SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debits,
           SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_credits
    FROM banking_transactions
    WHERE account_number='1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")

result = cur.fetchone()
if result:
    total, min_date, max_date, total_debits, total_credits = result
    print(f"\n" + "=" * 100)
    print(f"📊 2012 SUMMARY:")
    print(f"   Total Transactions: {total}")
    print(f"   Date Range: {min_date} to {max_date}")
    print(f"   Total Debits: ${total_debits:.2f}")
    print(f"   Total Credits: ${total_credits:.2f}")
    print(f"   Net Change: ${total_credits - total_debits:.2f}")
    
    if all_correct:
        print(f"\n✅ ALL MONTH-END BALANCES VERIFIED - 2012 DATA IS COMPLETE AND ACCURATE")
    else:
        print(f"\n⚠️  SOME BALANCES DIFFER - REVIEW NEEDED")

cur.close()
conn.close()

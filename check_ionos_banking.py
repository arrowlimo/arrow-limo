import os, psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Look for IONOS payments in banking by description
cur.execute("""
SELECT 
    transaction_date,
    description, 
    debit_amount,
    credit_amount,
    COUNT(*) as cnt
FROM banking_transactions
WHERE description ILIKE '%IONOS%' 
   OR description ILIKE '%1&1%'
GROUP BY transaction_date, description, debit_amount, credit_amount
ORDER BY transaction_date DESC
LIMIT 50
""")

print("\nIONOS/1&1 Payments in Banking Transactions:\n")
print("-" * 100)
for date, desc, debit, credit, cnt in cur.fetchall():
    amt = debit if debit else credit
    print(f"{date} | {desc:40} | ${amt:8.2f} x{cnt}")

print("-" * 100)

# Get summary
cur.execute("""
SELECT COUNT(DISTINCT DATE(transaction_date)), SUM(debit_amount), COUNT(*)
FROM banking_transactions
WHERE description ILIKE '%IONOS%' OR description ILIKE '%1&1%'
""")
months, total, txns = cur.fetchone()
if total:
    print(f"\nTotal IONOS/1&1 in banking: {total:.2f} across {txns} transactions, {months} different dates")
else:
    print("\nNo IONOS/1&1 found in banking transactions")

conn.close()

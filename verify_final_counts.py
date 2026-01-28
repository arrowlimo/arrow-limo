import os, psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check exact counts
categories = [
    ('GoDaddy', "vendor_name ILIKE '%GoDaddy%'"),
    ('Wix', "vendor_name ILIKE '%Wix%'"),
    ('IONOS', "vendor_name ILIKE '%IONOS%' OR vendor_name ILIKE '%1&1%'"),
]

print("\nRECEIPTS BY VENDOR (Final Counts):\n")
for name, where in categories:
    cur.execute(f"SELECT COUNT(*), SUM(gross_amount), MIN(receipt_date), MAX(receipt_date) FROM receipts WHERE {where}")
    cnt, amt, min_d, max_d = cur.fetchone()
    if cnt:
        print(f"{name:20} {cnt:6,} records  ${amt:>12,.2f}  [{min_d} to {max_d}]")

# Check banking counts
print("\nBANKING TRANSACTIONS BY ACCOUNT:\n")
cur.execute("""
SELECT account_number, COUNT(*), MIN(transaction_date), MAX(transaction_date)
FROM banking_transactions
GROUP BY account_number
ORDER BY account_number
""")
for acct, cnt, min_d, max_d in cur.fetchall():
    print(f"{acct:20} {cnt:6,} records  [{min_d} to {max_d}]")

conn.close()

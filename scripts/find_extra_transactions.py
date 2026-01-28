import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Find the 2 extra transactions
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        source_file
    FROM banking_transactions
    WHERE account_number = '0228362'
        AND transaction_date IN ('2018-07-09', '2018-02-06')
    ORDER BY transaction_date
""")

print("TRANSACTIONS TO REMOVE (not in bank CSV):")
print()

rows = cur.fetchall()
for txn_id, date, desc, debit, credit, source in rows:
    amt = debit if debit else credit
    print(f"ID: {txn_id} | {date} | ${amt:.2f} | {desc}")
    print(f"  Source: {source}")
    print()

if rows:
    print("=" * 75)
    print("These transactions exist in the database but NOT in the bank CSV.")
    print("They should be deleted since the bank CSV is the authoritative source.")
    print()
    ids_to_delete = [str(row[0]) for row in rows]
    ids_str = ','.join(ids_to_delete)
    print(f"To delete, run:")
    print(f"DELETE FROM banking_transactions WHERE transaction_id IN ({ids_str});")
    print()

cur.close()
conn.close()

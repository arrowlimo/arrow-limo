import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("Checking for Jan 2, 2013 transactions in Scotia account:")
print("="*80)

cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND transaction_date = '2013-01-02'
    ORDER BY transaction_id
""")

rows = cur.fetchall()
print(f'\nJan 2, 2013 transactions found: {len(rows)}')

if rows:
    for r in rows:
        desc = r[2][:60] if r[2] else "N/A"
        print(f'  ID {r[0]} | {r[1]} | {desc} | Debit:{r[3]} Credit:{r[4]}')
else:
    print("  NO TRANSACTIONS FOUND FOR JAN 2, 2013")
    print("\n  This confirms the gap - we're missing Jan 2 data!")

print("\n" + "="*80)
print("\nMissing amounts from PDF (should be on Jan 2, 2013):")
print("  - $193.00 (DEPOSIT)")
print("  - $594.98 (DEPOSIT)")
print("  - $102.35 (DEPOSIT)")
print("  - $165.00 (DEPOSIT)")
print("  - $205.00 (DEPOSIT)")

cur.close()
conn.close()

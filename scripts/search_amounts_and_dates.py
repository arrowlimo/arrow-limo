import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Search for the specific amounts across ALL years and accounts
print("SEARCHING FOR $520.93 ACROSS ALL BANKING TRANSACTIONS:")
print()

cur.execute("""
    SELECT 
        transaction_id,
        account_number,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        source_file,
        import_batch
    FROM banking_transactions
    WHERE (debit_amount = 520.93 OR credit_amount = 520.93)
    ORDER BY transaction_date
""")

rows = cur.fetchall()
print(f"{'ID':<8} {'Account':<12} {'Date':<12} {'Amount':>10} {'Description':<45} {'Source':<20} {'Batch':<20}")
print("-" * 130)

for txn_id, acct, date, desc, debit, credit, source, batch in rows:
    amt = debit if debit else credit
    source_display = source if source else "(manual)"
    batch_display = batch if batch else "(none)"
    print(f"{txn_id:<8} {acct:<12} {date:<12} ${amt:>9.2f} {desc:<43} {source_display:<20} {batch_display:<20}")

print()
print("=" * 130)
print()
print("SEARCHING FOR $1921.28 ACROSS ALL BANKING TRANSACTIONS:")
print()

cur.execute("""
    SELECT 
        transaction_id,
        account_number,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        source_file,
        import_batch
    FROM banking_transactions
    WHERE (debit_amount = 1921.28 OR credit_amount = 1921.28)
    ORDER BY transaction_date
""")

rows = cur.fetchall()
print(f"{'ID':<8} {'Account':<12} {'Date':<12} {'Amount':>10} {'Description':<45} {'Source':<20} {'Batch':<20}")
print("-" * 130)

for txn_id, acct, date, desc, debit, credit, source, batch in rows:
    amt = debit if debit else credit
    source_display = source if source else "(manual)"
    batch_display = batch if batch else "(none)"
    print(f"{txn_id:<8} {acct:<12} {date:<12} ${amt:>9.2f} {desc:<43} {source_display:<20} {batch_display:<20}")

print()
print("=" * 130)
print()
print("CHECKING FOR DATE TYPOS (2025 instead of 2018/2019) IN ACCOUNT 0228362:")
print()

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
        AND EXTRACT(YEAR FROM transaction_date) = 2025
    ORDER BY transaction_date
""")

rows = cur.fetchall()
if rows:
    print(f"{'ID':<8} {'Date':<12} {'Amount':>10} {'Description':<50} {'Source':<20}")
    print("-" * 100)
    for txn_id, date, desc, debit, credit, source in rows:
        amt = debit if debit else credit
        source_display = source if source else "(manual)"
        print(f"{txn_id:<8} {date:<12} ${amt:>9.2f} {desc:<48} {source_display:<20}")
else:
    print("No 2025 dates found in account 0228362")

print()
print("=" * 130)
print()
print("CHECKING FOR UNUSUAL DATES IN ACCOUNT 0228362 (outside normal range):")
print()

cur.execute("""
    SELECT DISTINCT EXTRACT(YEAR FROM transaction_date) as year
    FROM banking_transactions
    WHERE account_number = '0228362'
    ORDER BY year
""")

years = [int(row[0]) for row in cur.fetchall()]
print(f"Years present in 0228362 account: {years}")

cur.close()
conn.close()

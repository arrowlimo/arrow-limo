"""
Check 8362 account info and verified column stats.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Confirm 8362 account number
cur.execute("SELECT DISTINCT account_number FROM banking_transactions WHERE account_number LIKE '%8362%'")
print("8362 account_number values:", [r[0] for r in cur.fetchall()])

# Verified stats for 8362
cur.execute("""
    SELECT verified, COUNT(*)
    FROM banking_transactions WHERE account_number='0228362'
    GROUP BY verified ORDER BY verified
""")
print("8362 verified breakdown:")
for r in cur.fetchall():
    print(f"  verified={r[0]}  count={r[1]}")

# Check receipt_banking_links count for 8362
cur.execute("""
    SELECT COUNT(DISTINCT bt.transaction_id)
    FROM banking_transactions bt
    JOIN receipt_banking_links rbl ON rbl.transaction_id = bt.transaction_id
    WHERE bt.account_number='0228362'
""")
print(f"8362 txns WITH receipt links: {cur.fetchone()[0]}")

# Check for any import_batch info on 1615 missing txns
cur.execute("""
    SELECT DISTINCT source_file, import_batch
    FROM banking_transactions WHERE account_number='1615'
    AND transaction_date < '2015-01-01'
    ORDER BY source_file
    LIMIT 20
""")
print("1615 source/batch info:")
for r in cur.fetchall():
    print(f"  source={r[0]}  batch={r[1]}")

conn.close()

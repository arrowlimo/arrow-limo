import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Delete the old placeholder OVERDRAFT INTEREST entries with NULL balance
cur.execute("""
    DELETE FROM banking_transactions
    WHERE account_number = '0228362'
    AND description = 'OVERDRAFT INTEREST'
    AND balance IS NULL
    AND transaction_date IN ('2014-11-30', '2014-12-31')
""")

deleted = cur.rowcount
conn.commit()
conn.close()

print(f"✓ Deleted {deleted} old placeholder OVERDRAFT INTEREST entries")

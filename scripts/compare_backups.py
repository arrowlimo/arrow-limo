import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check counts in 3 backups for Feb 2012
print("Feb 2012 row counts in backups:\n")

for table in [
    'banking_transactions_scotia_backup_20251124_221239',
    'banking_transactions_scotia_2012_2013_backup_20251203',
    'banking_transactions_scotia_2012_backup_20251207_140858'
]:
    try:
        cur.execute(f"""
            SELECT COUNT(*) 
            FROM {table}
            WHERE account_number = '903990106011'
            AND transaction_date BETWEEN '2012-02-01' AND '2012-02-29';
        """)
        count = cur.fetchone()[0]
        print(f"{table}: {count} rows")
    except Exception as e:
        print(f"{table}: ERROR - {e}")

# Also check current table
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND transaction_date BETWEEN '2012-02-01' AND '2012-02-29';
""")
count = cur.fetchone()[0]
print(f"\nbanking_transactions (current): {count} rows")

cur.close()
conn.close()

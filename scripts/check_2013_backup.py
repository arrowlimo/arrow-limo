"""Check 2013 backup to see if it has the original NULL balances."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Check backup
cur.execute("""
    SELECT COUNT(*) as total,
           COUNT(CASE WHEN balance IS NULL THEN 1 END) as null_count
    FROM banking_transactions_1615_backup_2013
""")

row = cur.fetchone()
print(f"2013 Backup: {row[0]} txns, {row[1]} with NULL balance")

# Check first few
cur.execute("""
    SELECT transaction_date, description, balance 
    FROM banking_transactions_1615_backup_2013
    ORDER BY transaction_date ASC, transaction_id ASC
    LIMIT 5
""")

print("\nFirst 5 transactions in backup:")
for row in cur.fetchall():
    balance_str = f"${row[2]}" if row[2] is not None else "NULL"
    print(f"  {row[0]} | {row[1][:40]} | {balance_str}")

conn.close()

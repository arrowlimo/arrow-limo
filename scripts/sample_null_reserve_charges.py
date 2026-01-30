import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("Sample charges with NULL or empty reserve_number:")
print()

cur.execute("""
    SELECT reserve_number, account_number, description, amount, created_at, charge_type
    FROM charter_charges
    WHERE reserve_number IS NULL OR reserve_number = ''
    ORDER BY amount DESC
    LIMIT 15
""")

for reserve, account, desc, amt, created, ctype in cur.fetchall():
    print(f"{reserve or 'NULL':10} | {account or 'NULL':15} | {desc[:40]:40} | ${amt:>10.2f} | {ctype or 'NULL'}")

print("\nCount by account_number:")
cur.execute("""
    SELECT account_number, COUNT(*), SUM(amount)
    FROM charter_charges
    WHERE reserve_number IS NULL OR reserve_number = ''
    GROUP BY account_number
    ORDER BY COUNT(*) DESC
    LIMIT 10
""")

for acct, count, total in cur.fetchall():
    print(f"  {acct or 'NULL':20} {count:>6,} charges ${total:>12,.2f}")

cur.close()
conn.close()

"""
Quick sample of unmatched payments with payment_key and deposit notes.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 120)
print("UNMATCHED PAYMENTS WITH PAYMENT_KEY")
print("=" * 120)
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_key, account_number, notes
    FROM payments
    WHERE reserve_number IS NULL
      AND payment_date >= '2007-01-01'
      AND payment_date < '2025-01-01'
      AND payment_key IS NOT NULL
    ORDER BY payment_date DESC
    LIMIT 20
""")

for row in cur.fetchall():
    pid, pdate, amount, pkey, account, notes = row
    print(f"Payment {pid}: ${amount if amount else 0:.2f} on {pdate}, Key: {pkey}, Account: {account if account else 'NULL'}")
    print(f"  Notes: {notes[:100] if notes else 'NULL'}")
    print()

print("\n" + "=" * 120)
print("UNMATCHED PAYMENTS WITH 'DEPOSIT' IN NOTES")
print("=" * 120)
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_key, account_number, notes
    FROM payments
    WHERE reserve_number IS NULL
      AND payment_date >= '2007-01-01'
      AND payment_date < '2025-01-01'
      AND notes ILIKE '%deposit%'
    ORDER BY payment_date DESC
    LIMIT 20
""")

for row in cur.fetchall():
    pid, pdate, amount, pkey, account, notes = row
    print(f"Payment {pid}: ${amount if amount else 0:.2f} on {pdate}, Key: {pkey if pkey else 'NULL'}")
    print(f"  Notes: {notes[:100] if notes else 'NULL'}")
    print()

cur.close()
conn.close()

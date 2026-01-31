import psycopg2
import psycopg2.extras
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    dbname=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

print("PostgreSQL payments for Reserve 012219:")
cur.execute("""
    SELECT payment_id, payment_key, reserve_number, 
           COALESCE(payment_amount, amount, 0) as amount,
           payment_date, payment_method, status, created_at
    FROM payments 
    WHERE reserve_number = '012219'
    ORDER BY payment_date, payment_id
""")
rows = cur.fetchall()
print(f"Total: {len(rows)} payments\n")

batch_payments = []
non_batch_payments = []

for r in rows:
    if r['payment_key']:
        batch_payments.append(r)
    else:
        non_batch_payments.append(r)

print(f"IN BATCH 0012980: {len(batch_payments)} payments")
for r in batch_payments:
    print(f"  Payment {r['payment_id']}: ${r['amount']:.2f} on {r['payment_date']}, method={r['payment_method']}")

print(f"\nNOT IN BATCH (no payment_key): {len(non_batch_payments)} payments")
for r in non_batch_payments:
    print(f"  Payment {r['payment_id']}: ${r['amount']:.2f} on {r['payment_date']}, method={r['payment_method'] or 'NULL'}")

print("\n" + "="*60)
print("LMS shows 3 payments (from your screenshot):")
print("  02/20/2016 Visa    RECEIVED  195.00 2sph")
print("  02/22/2016 Visa    RECEIVED  401.52")  
print("  02/22/2016 Cash    RECEIVED  200.00")
print("="*60)

cur.close()
conn.close()

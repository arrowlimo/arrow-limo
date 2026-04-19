import psycopg2
from psycopg2.extras import RealDictCursor

DB_PARAMS = {
    "host": "localhost",
    "port": 5432,
    "database": "almsdata",
    "user": "postgres",
    "password": "ArrowLimousine",
}


def run_update(cur, label, pattern, category, note):
    sql = """
    UPDATE banking_transactions
    SET category = %s,
        reconciliation_status = 'MANUAL_CLASSIFIED',
        reconciliation_notes = %s,
        updated_at = NOW()
    WHERE debit_amount > 0
      AND receipt_id IS NULL
      AND (
            description ILIKE '%%etransfer%%'
            OR description ILIKE '%%e-transfer%%'
            OR description ILIKE '%%email transfer%%'
          )
      AND description ILIKE %s
      AND reconciliation_status IS DISTINCT FROM 'MANUAL_CLASSIFIED'
    RETURNING transaction_id, debit_amount;
    """
    cur.execute(sql, (category, note, pattern))
    rows = cur.fetchall()
    count = len(rows)
    amt = sum(float(r["debit_amount"] or 0) for r in rows)
    print(f"{label}: {count} rows, ${amt:,.2f}")
    return count, amt


conn = psycopg2.connect(**DB_PARAMS)
cur = conn.cursor(cursor_factory=RealDictCursor)

total_count = 0
total_amt = 0.0

rules = [
    ("CRYSTAL_CLEANER", "%crystal driver clea%", "VENDOR_SERVICE", "Vehicle cleaning/detail service"),
    ("SHAUN_IMAGE_LIMO", "%image limo%", "VENDOR_SERVICE", "Vehicle image/branding related service"),
    ("JAX_WEBB_PEACOCK", "%jax webb peacock%", "DRIVER_PAY_REIMBURSEMENT", "Peacock-family related reimburse transfer"),
    ("LYNDA_SIMMERLINK", "%lynda simmerlink%", "CLIENT_REFUND", "Client refund (Linda/Lynda variant)"),
    ("LYNDA_SIMMELINK", "%lynda simmelink%", "CLIENT_REFUND", "Client refund (Linda/Lynda variant)"),
]

for label, pattern, category, note in rules:
    c, a = run_update(cur, label, pattern, category, note)
    total_count += c
    total_amt += a

conn.commit()
cur.close()
conn.close()

print("=" * 80)
print(f"TOTAL_UPDATED: {total_count} rows, ${total_amt:,.2f}")
print("=" * 80)

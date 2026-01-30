import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
# Set isolation level after connection
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("DATABASE CONSOLIDATION STATUS")
print("=" * 80)

# Check charges
cur.execute("SELECT COUNT(*) as count FROM charter_charges")
charges_count = cur.fetchone()['count']
print(f"\ncharter_charges: {charges_count:,} rows")

cur.execute("SELECT charge_type, COUNT(*) as count FROM charter_charges GROUP BY charge_type ORDER BY count DESC")
for row in cur.fetchall():
    print(f"  {row['charge_type']}: {row['count']:,}")

# Check payments
cur.execute("SELECT COUNT(*) as count FROM charter_payments")
payments_count = cur.fetchone()['count']
print(f"\ncharter_payments: {payments_count:,} rows")

cur.execute("SELECT source, COUNT(*) as count FROM charter_payments GROUP BY source ORDER BY count DESC")
for row in cur.fetchall():
    source = row['source'] or 'NULL'
    print(f"  {source}: {row['count']:,}")

# Check batch_deposit_allocation payments
cur.execute("""
    SELECT COUNT(*) as count 
    FROM charter_payments 
    WHERE source = 'batch_deposit_allocation'
""")
bda_payments = cur.fetchone()['count']
print(f"\n  batch_deposit_allocation payments: {bda_payments:,}")

cur.execute("""
    SELECT COUNT(*) as count 
    FROM charter_payments 
    WHERE payment_key LIKE 'BDA_%'
""")
bda_key_payments = cur.fetchone()['count']
print(f"  BDA_* payment_key payments: {bda_key_payments:,}")

# Sample BDA payments
if bda_key_payments > 0:
    cur.execute("""
        SELECT payment_key, amount, payment_date, charter_id
        FROM charter_payments 
        WHERE payment_key LIKE 'BDA_%'
        LIMIT 5
    """)
    print(f"\n  Sample BDA payments:")
    for row in cur.fetchall():
        print(f"    {row['payment_key']}: ${row['amount']} on {row['payment_date']} for charter {row['charter_id']}")

# Check refund payments
cur.execute("""
    SELECT COUNT(*) as count 
    FROM charter_payments 
    WHERE source = 'refund' OR source = 'charter_refund'
""")
refund_payments = cur.fetchone()['count']
print(f"  refund payments (by source): {refund_payments:,}")

cur.execute("""
    SELECT COUNT(*) as count 
    FROM charter_payments 
    WHERE payment_key LIKE 'REFUND_%'
""")
refund_key_payments = cur.fetchone()['count']
print(f"  REFUND_* payment_key payments: {refund_key_payments:,}")

# Check what was created today
cur.execute("""
    SELECT COUNT(*) as count 
    FROM charter_payments 
    WHERE imported_at::date = CURRENT_DATE
""")
today_payments = cur.fetchone()['count']
print(f"\nPayments imported today: {today_payments:,}")

cur.execute("""
    SELECT COUNT(*) as count 
    FROM charter_charges 
    WHERE created_at::date = CURRENT_DATE
""")
today_charges = cur.fetchone()['count']
print(f"Charges created today: {today_charges:,}")

cur.close()
conn.close()

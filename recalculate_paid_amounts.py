import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("Recalculating paid_amount and balance from actual payments...\n")

# Create backup
cur.execute("""
    SELECT COUNT(*) FROM charters WHERE paid_amount != (
        SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = charters.reserve_number
    )
""")
mismatch_count = cur.fetchone()[0]

print(f"Found {mismatch_count} charters with paid_amount mismatches\n")

# Recalculate paid_amount based on actual payments
sql_update = """
    UPDATE charters c
    SET 
        paid_amount = COALESCE(p.total_paid, 0),
        balance = c.total_amount_due - COALESCE(p.total_paid, 0)
    FROM (
        SELECT reserve_number, SUM(amount) as total_paid
        FROM payments
        GROUP BY reserve_number
    ) p
    WHERE c.reserve_number = p.reserve_number
    AND c.paid_amount != COALESCE(p.total_paid, 0)
"""

cur.execute(sql_update)
updated = cur.rowcount
conn.commit()

print(f"✅ Updated {updated} charters with recalculated paid_amount and balance")

# Verify fixes
cur.execute("""
    SELECT COUNT(*) FROM charters WHERE paid_amount = (
        SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = charters.reserve_number
    )
""")
matched = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM charters WHERE status IS NOT NULL AND status NOT IN ('cancelled', 'refunded')")
total_active = cur.fetchone()[0]

print(f"\nFinal Payment Matching Status:")
print(f"  Charters with matching paid_amount: {matched:,}")
print(f"  Total active charters:              {total_active:,}")
print(f"  Match rate:                         {100*matched/total_active:.1f}%")

cur.close()
conn.close()

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("Removing penny rounding from payments and charters...\n")

# Remove from payments
try:
    cur.execute("DROP TRIGGER IF EXISTS round_payments_amount ON payments")
    conn.commit()
    print("✅ Dropped rounding trigger from payments")
except Exception as e:
    print(f"⚠️  Error: {e}")
    conn.rollback()

try:
    cur.execute("""
        ALTER TABLE payments
        DROP CONSTRAINT IF EXISTS amount_rounded_penny
    """)
    conn.commit()
    print("✅ Dropped rounding constraint from payments")
except Exception as e:
    print(f"⚠️  Error: {e}")
    conn.rollback()

# Remove from charters
try:
    cur.execute("DROP TRIGGER IF EXISTS round_charter_totals ON charters")
    conn.commit()
    print("✅ Dropped rounding trigger from charters")
except Exception as e:
    print(f"⚠️  Error: {e}")
    conn.rollback()

try:
    cur.execute("""
        ALTER TABLE charters
        DROP CONSTRAINT IF EXISTS total_amount_due_rounded_penny
    """)
    conn.commit()
    print("✅ Dropped rounding constraint from charters")
except Exception as e:
    print(f"⚠️  Error: {e}")
    conn.rollback()

print("\n" + "="*70)
print("✅ PENNY ROUNDING - CHARTER_CHARGES ONLY")
print("="*70)
print("Rounding is now ONLY enforced on charter_charges.amount")
print("Payments and charters tables use native precision")

cur.close()
conn.close()

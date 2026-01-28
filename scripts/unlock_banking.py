"""
Disable banking lock trigger to allow QB duplicate cleanup.
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("DISABLE BANKING LOCK")
print("=" * 80)

# Drop the trigger
print("\nDropping enforce_banking_lock_trigger...")
cur.execute("""
    DROP TRIGGER IF EXISTS enforce_banking_lock_trigger ON banking_transactions
""")
print("✅ Trigger dropped")

# Drop the function
print("\nDropping enforce_banking_lock function...")
cur.execute("""
    DROP FUNCTION IF EXISTS enforce_banking_lock() CASCADE
""")
print("✅ Function dropped")

conn.commit()
print("\n✅ Banking lock disabled - you can now modify 2012-2014 data")

cur.close()
conn.close()

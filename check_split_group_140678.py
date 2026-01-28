"""Check for split receipts created from 140678"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

# Check for receipts with split_group_id = 140678
cur.execute("""
    SELECT receipt_id, gl_account_code, gross_amount, payment_method, description
    FROM receipts 
    WHERE split_group_id = 140678
    ORDER BY receipt_id
""")
rows = cur.fetchall()

if rows:
    print(f"\n✅ Found {len(rows)} split receipts from original 140678:")
    total = 0
    for r in rows:
        print(f"   Receipt {r[0]}: GL {r[1]} = ${r[2]:.2f} ({r[3]}) - {r[4]}")
        total += r[2]
    print(f"\n   Total: ${total:.2f}")
else:
    print("\n❌ No split receipts found with split_group_id = 140678")
    
# Check if original still exists
cur.execute("SELECT COUNT(*) FROM receipts WHERE receipt_id = 140678")
if cur.fetchone()[0] > 0:
    print("\n⚠️  Original receipt 140678 still exists (not deleted)")
else:
    print("\n✅ Original receipt 140678 was deleted as expected")

cur.close()
conn.close()

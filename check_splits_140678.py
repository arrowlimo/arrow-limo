"""Check if splits were created for receipt 140678"""
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

# Check receipt status
cur.execute("""
    SELECT receipt_id, gross_amount, vendor_name
    FROM receipts WHERE receipt_id = 140678
""")
receipt = cur.fetchone()
print(f"\n📄 Receipt {receipt[0]}: ${receipt[1]:.2f} - {receipt[2]}")

# Check splits
cur.execute("""
    SELECT split_id, gl_code, split_amount, description 
    FROM receipt_splits 
    WHERE receipt_id = 140678 
    ORDER BY split_id
""")
rows = cur.fetchall()
print(f"\n✅ Splits created: {len(rows)}")
total = 0
for r in rows:
    print(f"   Split {r[0]}: GL {r[1]} = ${r[2]:.2f} ({r[3]})")
    total += r[2]
    
if len(rows) > 0:
    print(f"\n   Total: ${total:.2f}")
    if abs(total - receipt[1]) < 0.01:
        print(f"   ✅ Splits match receipt total!")
    else:
        print(f"   ❌ Splits don't match receipt (diff: ${abs(total - receipt[1]):.2f})")

cur.close()
conn.close()

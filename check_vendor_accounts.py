import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Check what vendors exist
cur.execute("""
    SELECT account_id, canonical_vendor, display_name, status
    FROM vendor_accounts
    ORDER BY canonical_vendor
    LIMIT 20
""")

print("VENDOR ACCOUNTS:")
rows = cur.fetchall()
if rows:
    for account_id, canonical_vendor, display_name, status in rows:
        print(f"  {account_id}: {canonical_vendor} ({display_name}) - {status}")
else:
    print("  No vendor accounts found")

# Check if WCB exists in receipts
cur.execute("""
    SELECT DISTINCT vendor_name 
    FROM receipts 
    WHERE vendor_name ILIKE '%wcb%'
    LIMIT 10
""")

print("\nWCB references in receipts:")
wcb_rows = cur.fetchall()
if wcb_rows:
    for row in wcb_rows:
        print(f"  {row[0]}")
else:
    print("  No WCB entries found")

cur.close()
conn.close()

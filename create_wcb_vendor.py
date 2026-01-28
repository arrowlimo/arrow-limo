import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Create vendor account for WCB
cur.execute("""
    INSERT INTO vendor_accounts (canonical_vendor, display_name, status, created_at)
    VALUES (%s, %s, %s, NOW())
    ON CONFLICT (canonical_vendor) DO NOTHING
""", ('WCB', 'Workers Compensation Board of Alberta', 'active'))

conn.commit()

# Check if it was created
cur.execute("""
    SELECT account_id, canonical_vendor, display_name, status
    FROM vendor_accounts 
    WHERE canonical_vendor = 'WCB'
""")

result = cur.fetchone()
if result:
    print(f"✅ Created WCB vendor account: {result}")
else:
    print("❌ Failed to create WCB vendor account")

cur.close()
conn.close()

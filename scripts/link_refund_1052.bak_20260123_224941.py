import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Link refund #1052 to charter 013429
cur.execute("""
    UPDATE charter_refunds 
    SET charter_id = (SELECT charter_id FROM charters WHERE reserve_number = '013429'),
        reserve_number = '013429',
        description = COALESCE(description, '') || ' | Linked to 013429 - duplicate charge ($850 = 2x $415.42)'
    WHERE id = 1052
""")

conn.commit()

# Verify the update
cur.execute('SELECT id, charter_id, reserve_number, amount FROM charter_refunds WHERE id = 1052')
result = cur.fetchone()
print(f"✓ Refund #1052 updated: ID={result[0]}, Charter={result[1]}, Reserve={result[2]}, Amount=${result[3]}")

# Check final status
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE charter_id IS NOT NULL) as linked,
        COUNT(*) as total
    FROM charter_refunds
""")
stats = cur.fetchone()
print(f"\nFinal linkage: {stats[0]}/{stats[1]} ({stats[0]/stats[1]*100:.1f}%)")

cur.close()
conn.close()

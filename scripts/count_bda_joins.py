import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

# Direct count of batch_deposit_allocations
cur.execute("SELECT COUNT(*) FROM batch_deposit_allocations")
bda_total = cur.fetchone()[0]
print(f"batch_deposit_allocations total: {bda_total:,}")

# Count JOINED with charters
cur.execute("""
    SELECT COUNT(*) 
    FROM batch_deposit_allocations bda
    JOIN charters c ON c.reserve_number = bda.reserve_number
""")
joined = cur.fetchone()[0]
print(f"batch_deposit_allocations JOIN charters: {joined:,}")

# Check LEFT JOIN (should be same as total if all match)
cur.execute("""
    SELECT COUNT(*) 
    FROM batch_deposit_allocations bda
    LEFT JOIN charters c ON c.reserve_number = bda.reserve_number
""")
left_joined = cur.fetchone()[0]
print(f"batch_deposit_allocations LEFT JOIN charters: {left_joined:,}")

# Count with NULL match
cur.execute("""
    SELECT COUNT(*) 
    FROM batch_deposit_allocations bda
    LEFT JOIN charters c ON c.reserve_number = bda.reserve_number
    WHERE c.reserve_number IS NULL
""")
unmatched = cur.fetchone()[0]
print(f"batch_deposit_allocations with NO matching charter: {unmatched:,}")

# Check for duplicates in batch_deposit_allocations
cur.execute("""
    SELECT COUNT(DISTINCT allocation_id) as distinct_ids, COUNT(*) as total_rows
    FROM batch_deposit_allocations
""")
row = cur.fetchone()
print(f"\nbatch_deposit_allocations:")
print(f"  Total rows: {row[1]:,}")
print(f"  Distinct allocation_id: {row[0]:,}")

cur.close()
conn.close()

import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*100)
print("INVESTIGATING BATCH_DEPOSIT_ALLOCATIONS WITHOUT MATCHING CHARTERS")
print("="*100)

# Find unmatched
cur.execute("""
    SELECT COUNT(DISTINCT bda.reserve_number) as count
    FROM batch_deposit_allocations bda
    LEFT JOIN charters c ON c.reserve_number = bda.reserve_number
    WHERE c.reserve_number IS NULL
""")
unmatched_count = cur.fetchone()['count']
print(f"\nUnique reserve_numbers in batch_deposit_allocations without matching charter: {unmatched_count}")

# Get samples
cur.execute("""
    SELECT DISTINCT bda.reserve_number
    FROM batch_deposit_allocations bda
    LEFT JOIN charters c ON c.reserve_number = bda.reserve_number
    WHERE c.reserve_number IS NULL
    ORDER BY bda.reserve_number
    LIMIT 20
""")

print(f"\nSample unmatched reserve_numbers:")
samples = cur.fetchall()
for row in samples:
    print(f"  {row['reserve_number']}")

# Count total allocations for unmatched reserves
cur.execute("""
    SELECT 
        COUNT(*) as allocation_count,
        SUM(allocation_amount) as total_amount
    FROM batch_deposit_allocations bda
    LEFT JOIN charters c ON c.reserve_number = bda.reserve_number
    WHERE c.reserve_number IS NULL
""")

result = cur.fetchone()
print(f"\nUnmatched allocations:")
print(f"  Count: {result['allocation_count']:,}")
print(f"  Total amount: ${result['total_amount']:,.2f}")

# Check if these reserves exist in ANY table
if unmatched_count > 0:
    cur.execute("""
        SELECT DISTINCT bda.reserve_number
        FROM batch_deposit_allocations bda
        LEFT JOIN charters c ON c.reserve_number = bda.reserve_number
        WHERE c.reserve_number IS NULL
        LIMIT 5
    """)
    
    sample_reserves = [row['reserve_number'] for row in cur.fetchall()]
    
    for reserve in sample_reserves:
        print(f"\n\nChecking reserve {reserve}:")
        
        # Check if it exists in charters
        cur.execute("SELECT COUNT(*) as count FROM charters WHERE reserve_number = %s", (reserve,))
        in_charters = cur.fetchone()['count']
        print(f"  In charters table: {in_charters > 0}")
        
        # Get sample allocation
        cur.execute("SELECT allocation_id, allocation_amount FROM batch_deposit_allocations WHERE reserve_number = %s LIMIT 1", (reserve,))
        alloc = cur.fetchone()
        if alloc:
            print(f"  Sample allocation: ID {alloc['allocation_id']}, ${alloc['allocation_amount']}")

cur.close()
conn.close()

print("\n" + "="*100)

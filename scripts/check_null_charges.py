import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT charter_id, reserve_number, description, amount, charge_type 
    FROM charter_charges 
    WHERE charter_id = 5795
""")

print("Charter 006852 (charter_id=5795) charges:")
for row in cur.fetchall():
    cid, res, desc, amt, ctype = row
    print(f"  {desc}: ${amt or 0:.2f} (type: {ctype or 'NULL'})")

print("\n" + "="*80)
print("Checking all charters with NULL/0 charge amounts...")

cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.total_amount_due,
        COUNT(*) as charge_count,
        COUNT(CASE WHEN cc.amount IS NULL OR cc.amount = 0 THEN 1 END) as null_or_zero_count
    FROM charters c
    INNER JOIN charter_charges cc ON c.charter_id = cc.charter_id
    WHERE c.total_amount_due > 0
    GROUP BY c.charter_id, c.reserve_number, c.total_amount_due
    HAVING COUNT(*) = COUNT(CASE WHEN cc.amount IS NULL OR cc.amount = 0 THEN 1 END)
    ORDER BY c.total_amount_due DESC
    LIMIT 20
""")

results = cur.fetchall()
print(f"\nCharters with ALL charges NULL or $0: {len(results)}")
for row in results[:10]:
    cid, res, total, count, null_count = row
    print(f"  {res}: total_due=${total:.2f}, {count} charges (all NULL/$0)")

cur.close()
conn.close()

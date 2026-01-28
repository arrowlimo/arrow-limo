"""
Check charter_charges source for reserves with $0 LMS Est_Charge
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os

ZERO_EST_WITH_CHARGES = ['013603', '015542', '015541', '017483', '015152', '016296', '017042', '017041', '017070', '015189', '015194', '015427', '015463', '017286', '016868']

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*120)
print("CHARTER_CHARGES SOURCE ANALYSIS FOR $0 LMS EST_CHARGE")
print("="*120)

for reserve in ZERO_EST_WITH_CHARGES:
    cur.execute("""
        SELECT c.reserve_number, c.charter_id, c.total_amount_due,
               cc.charge_id, cc.description, cc.amount, cc.created_at
        FROM charters c
        LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
        WHERE c.reserve_number = %s
        ORDER BY cc.created_at
    """, (reserve,))
    
    rows = cur.fetchall()
    if not rows:
        continue
    
    first = rows[0]
    print(f"\n{reserve} (charter_id={first['charter_id']}, total_amount_due=${first['total_amount_due']:.2f}):")
    
    for row in rows:
        if row['charge_id']:
            print(f"  - ${row['amount']:8.2f} | {row['description'][:70]} | {row['created_at']}")
        else:
            print(f"  - NO CHARGES")

cur.close()
conn.close()

import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect("dbname=almsdata user=postgres host=localhost password=ArrowLimousine")
cur = conn.cursor(cursor_factory=RealDictCursor)

# Check the 4 remaining exceptions
for reserve_no in ['001764', '001820', '005711', '005702']:
    cur.execute("""
    SELECT 
      reserve_number,
      charter_date,
      grand_total,
      paid_amount,
      balance_owing,
      notes,
      cancelled
    FROM charters
    WHERE reserve_number = %s
    """, (reserve_no,))
    
    row = cur.fetchone()
    if row:
        print(f"\n{reserve_no}:")
        for k, v in row.items():
            print(f"  {k}: {v}")
        
        # Check linked payments
        cur.execute("""
        SELECT payment_id, amount, payment_date, source, payment_method
        FROM charter_payments 
        WHERE charter_id = %s::text
        """, (reserve_no,))
        payments = cur.fetchall()
        print(f"  Linked payments: {len(payments)}")
        for p in payments:
            print(f"    {dict(p)}")
    else:
        print(f"\n{reserve_no}: NOT FOUND IN DATABASE")

conn.close()
